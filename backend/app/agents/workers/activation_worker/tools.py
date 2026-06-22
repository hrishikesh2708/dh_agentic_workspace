"""activation_worker node tools — Phase 7: DB activation.

Writes the confirmed pipeline configuration to the database:

  1. Upsert ProjectSourceModule (draft → active)
  2. Insert ProjectFieldMapping rows (one per approved mapping)
  3. Insert ProjectFunnelStage rows (if funnel_enabled)
  4. Insert ProjectIntegration rows (one per active destination)
  5. Insert ConnectorConfig snapshot
  6. Insert AuditLog entry
  7. Set pipeline_activated=True, integration_ids, activated_config_version

All writes are inside a single DB transaction — if any step fails,
the whole activation is rolled back and validation_phase_complete is reset
so the user can retry after fixing the issue.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage
from sqlmodel import col, select

from app.agents import deps
from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.models import (
    AuditLog,
    ConnectorConfig,
    ConnectorConfigStatus,
    DatahashSchema,
    Destination,
    IntegrationCreatedVia,
    IntegrationStatus,
    ProjectFieldMapping,
    ProjectFunnelStage,
    ProjectIntegration,
    ProjectSourceModule,
    SourceModuleStatus,
)
from app.schemas import MappingStatus

ACTIVATION_PHASE = "activation"


def _agent_event(message: str, status: str = "confirmed") -> AIMessage:
    return AIMessage(
        content=json.dumps(
            {
                "type": "agent_event",
                "status": status,
                "message": message,
                "phase": ACTIVATION_PHASE,
            }
        )
    )


def _config_hash(config: dict) -> str:
    """Stable SHA-256 of a dict (sorted keys)."""
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Node 1 — run_activation
# ---------------------------------------------------------------------------


async def run_activation(state: GlobalAgentState) -> dict[str, Any]:
    """Write the full pipeline to the database.

    Reads from state (set by all upstream phases) and writes to DB inside
    a single transaction. On success, returns pipeline_activated=True plus
    integration_ids and activated_config_version.
    """
    if not state.project_id:
        raise RuntimeError("project_id required for activation")
    if not state.source_connection_id:
        raise RuntimeError("source_connection_id required for activation — connection phase incomplete")

    project_id: UUID = state.project_id
    source_connection_id: UUID = state.source_connection_id

    async with deps.session_maker() as db:
        async with db.begin():
            # ------------------------------------------------------------------
            # Step 1: Upsert ProjectSourceModule
            # ------------------------------------------------------------------
            # Check if a module already exists (e.g. resumed session)
            existing_module = None
            if state.source_module_id:
                mod_result = await db.get(ProjectSourceModule, state.source_module_id)
                existing_module = mod_result

            if existing_module:
                existing_module.status = SourceModuleStatus.active
                existing_module.signal_type = state.signal_type
                existing_module.schema_snapshot = state.schema_snapshot or []
                db.add(existing_module)
                source_module_id: UUID = existing_module.id  # type: ignore[assignment]
            else:
                module = ProjectSourceModule(
                    id=uuid4(),
                    project_connection_id=source_connection_id,
                    source_object=state.source_object,
                    display_name=state.source_object,
                    signal_type=state.signal_type,
                    status=SourceModuleStatus.active,
                    schema_snapshot=state.schema_snapshot or [],
                )
                db.add(module)
                await db.flush()
                source_module_id = module.id  # type: ignore[assignment]

            # ------------------------------------------------------------------
            # Step 2: Resolve canonical_key → DatahashSchema.id
            # ------------------------------------------------------------------
            all_canonical_keys = list({m.destination_field for m in state.mappings if m.destination_field})
            schema_result = await db.execute(
                select(DatahashSchema).where(
                    col(DatahashSchema.canonical_key).in_(all_canonical_keys),
                    col(DatahashSchema.is_deleted).is_(False),
                )
            )
            schema_rows = schema_result.scalars().all()
            key_to_schema_id: dict[str, int] = {s.canonical_key: s.id for s in schema_rows if s.id is not None}

            # ------------------------------------------------------------------
            # Step 3: Insert ProjectFieldMapping rows
            # ------------------------------------------------------------------
            # Mark existing rows as tombstone first (upsert-like behaviour)
            existing_fm_result = await db.execute(
                select(ProjectFieldMapping).where(
                    col(ProjectFieldMapping.source_module_id) == source_module_id,
                    col(ProjectFieldMapping.is_deleted).is_(False),
                )
            )
            for existing_fm in existing_fm_result.scalars().all():
                existing_fm.is_tombstone = True
                db.add(existing_fm)

            approved_statuses = {
                MappingStatus.human_approved,
                MappingStatus.auto_approved,
                MappingStatus.human_corrected,
            }

            for mapping in state.mappings:
                if not mapping.destination_field or not mapping.source_field:
                    continue
                if mapping.status not in approved_statuses:
                    continue

                schema_id = key_to_schema_id.get(mapping.destination_field)
                if not schema_id:
                    logger.warning(
                        "activation_schema_id_missing",
                        canonical_key=mapping.destination_field,
                    )
                    continue

                is_constant = mapping.source_field.startswith("__constant__:")
                constant_value: str | None = None
                source_field_path: str | None = None

                if is_constant:
                    constant_value = mapping.source_field.split(":", 1)[1]
                else:
                    source_field_path = mapping.source_field

                fm = ProjectFieldMapping(
                    id=uuid4(),
                    source_module_id=source_module_id,
                    datahash_schema_id=schema_id,
                    source_field_path=source_field_path,
                    is_constant=is_constant,
                    constant_value=constant_value,
                    confidence=mapping.confidence,
                    confirmed_by=f"user:{state.user_id}",
                    confirmed_at=datetime.now(timezone.utc),
                    is_tombstone=False,
                )
                db.add(fm)

            # ------------------------------------------------------------------
            # Step 4: Insert ProjectFunnelStage rows (if funnel_enabled)
            # ------------------------------------------------------------------
            if state.funnel_enabled and state.funnel_stages:
                # Delete previous funnel stages for this module
                existing_stages_result = await db.execute(
                    select(ProjectFunnelStage).where(
                        col(ProjectFunnelStage.source_module_id) == source_module_id,
                        col(ProjectFunnelStage.is_deleted).is_(False),
                    )
                )
                for stage in existing_stages_result.scalars().all():
                    stage.is_deleted = True
                    db.add(stage)

                for stage_dict in state.funnel_stages:
                    funnel_stage = ProjectFunnelStage(
                        id=uuid4(),
                        source_module_id=source_module_id,
                        stage_order=stage_dict.get("stage_order", 0),
                        stage_name=stage_dict.get("stage_name", ""),
                        trigger_field=stage_dict.get("trigger_field"),
                        trigger_value=stage_dict.get("trigger_value"),
                        time_field=stage_dict.get("time_field"),
                        value_field=stage_dict.get("value_field"),
                        per_destination=stage_dict.get("per_destination") or {},
                    )
                    db.add(funnel_stage)

            # ------------------------------------------------------------------
            # Step 5: Insert ProjectIntegration rows (one per active destination)
            # ------------------------------------------------------------------
            # Resolve destination slugs → Destination rows
            dest_result = await db.execute(
                select(Destination).where(
                    col(Destination.name).in_(state.active_destinations),
                    col(Destination.is_deleted).is_(False),
                )
            )
            dest_rows = {d.name: d for d in dest_result.scalars().all()}

            integration_ids: dict[str, str] = {}
            now = datetime.now(timezone.utc)

            for dest_slug in state.active_destinations:
                dest_row = dest_rows.get(dest_slug)
                if not dest_row:
                    logger.warning("activation_destination_not_found", slug=dest_slug)
                    continue

                dest_conn_id_str = state.destination_connection_ids.get(dest_slug)
                if not dest_conn_id_str:
                    logger.warning("activation_dest_conn_id_missing", slug=dest_slug)
                    continue

                dest_conn_id = UUID(dest_conn_id_str)

                integration = ProjectIntegration(
                    id=uuid4(),
                    source_module_id=source_module_id,
                    destination_conn_id=dest_conn_id,
                    destination_id=dest_row.id,  # type: ignore[arg-type]
                    status=IntegrationStatus.active,
                    created_via=IntegrationCreatedVia.copilot,
                    activated_at=now,
                    activated_by=f"user:{state.user_id}",
                )
                db.add(integration)
                await db.flush()
                integration_ids[dest_slug] = str(integration.id)

            # ------------------------------------------------------------------
            # Step 6: Insert ConnectorConfig snapshot
            # ------------------------------------------------------------------
            config_payload = {
                "source_object": state.source_object,
                "signal_type": state.signal_type,
                "funnel_enabled": state.funnel_enabled,
                "funnel_stages": state.funnel_stages,
                "mappings": [m.model_dump() for m in state.mappings],
                "destinations": state.active_destinations,
            }
            config_hash = _config_hash(config_payload)

            connector_config = ConnectorConfig(
                id=uuid4(),
                project_id=project_id,
                source_module_id=source_module_id,
                config_version=1,
                status=ConnectorConfigStatus.active,
                config_hash=config_hash,
                config=config_payload,
            )
            db.add(connector_config)
            await db.flush()
            config_version = connector_config.config_version

            # ------------------------------------------------------------------
            # Step 7: AuditLog
            # ------------------------------------------------------------------
            audit = AuditLog(
                id=uuid4(),
                project_id=project_id,
                source_module_id=source_module_id,
                action="pipeline_activated",
                detail={
                    "source_object": state.source_object,
                    "signal_type": state.signal_type,
                    "destinations": state.active_destinations,
                    "integration_ids": integration_ids,
                    "config_version": config_version,
                    "activated_by": f"user:{state.user_id}",
                },
            )
            db.add(audit)

    logger.info(
        "pipeline_activated",
        project_id=str(project_id),
        source_object=state.source_object,
        integration_ids=integration_ids,
    )

    # Build integration summary with activated vs deferred split
    import datetime as _dt

    active_dests = list(getattr(state, "active_destinations", []) or [])
    deferred_dests = list(getattr(state, "deferred_destinations", []) or [])
    channel_statuses = getattr(state, "channel_statuses", {}) or {}

    fully_activated = [d for d in active_dests if channel_statuses.get(d) == "connected"]

    integration_summary = {
        "activated": fully_activated,
        "deferred": deferred_dests,
        "activation_time": _dt.datetime.utcnow().isoformat() + "Z",
    }

    return {
        "pipeline_activated": True,
        "source_module_id": source_module_id,
        "integration_ids": integration_ids,
        "activated_config_version": config_version,
        "integration_summary": integration_summary,
        "messages": [
            _agent_event(
                f"Pipeline activated — {state.source_object} → {', '.join(state.active_destinations)}",
                status="confirmed",
            )
        ],
    }
