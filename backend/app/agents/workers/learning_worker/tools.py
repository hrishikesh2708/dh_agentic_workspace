"""learning_worker pipeline agent + session persistence helpers.

Ported from three crawler_agent files:

- ``src/persistence/sessions.py``       → :func:`persist_session`,
   :func:`apply_review_response`
- ``src/pipeline/feedback_learner.py``  → :class:`FeedbackLearningAgent`

ORM models live in :mod:`app.models`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlmodel import col

from app.agents.core.agent_config import _AgentSettingsProxy
from app.agents.shared_tools.openai_client import OpenAIService
from app.agents.shared_tools.vector_store import VectorStoreService
from app.core.metrics import (
    golden_rule_hits_total,
    mapping_runs_total,
)
from app.models.field_mapping import FieldMapping
from app.models.golden_rule import GoldenRule
from app.models.mapping_session import MappingSession
from app.schemas.agent.types import MappingStatus


# -----------------------------------------------------------------------------
# Review-response application + session persistence
# (ported from src/persistence/sessions.py)
# -----------------------------------------------------------------------------


def apply_review_response(mappings: list[dict], response: Any) -> list[dict]:
    """Merge the client's HITL ``response`` payload into the mapping list.

    Verbatim port of ``src/persistence/sessions.py::apply_review_response``.
    Operates on (and returns) ``list[dict]`` because the HITL payload going
    over the wire is dict-shaped. The caller is responsible for converting
    back to :class:`ProposedMapping` before writing to state.
    """
    updated = [dict(m) for m in mappings]
    if not isinstance(response, dict):
        return updated

    approved_all = response.get("approved", True)
    review_map = {
        r["source_field"]: r for r in (response.get("reviews") or []) if isinstance(r, dict) and "source_field" in r
    }

    for i, m in enumerate(updated):
        src = m.get("source_field", "")
        if src in review_map:
            rev = review_map[src]
            updated[i] = {**m, "status": rev.get("status", "human_approved")}
            if "destination_field" in rev:
                dest = rev.get("destination_field")
                updated[i]["destination_field"] = dest if dest else None
        elif approved_all and m.get("status") in {"needs_review", "unmatched"}:
            updated[i] = {**m, "status": "human_approved"}

    return updated


def _has_destination(mapping) -> bool:
    """True if a :class:`ProposedMapping` has a non-empty destination_field."""
    dest = mapping.destination_field
    return bool(dest and str(dest).strip())


async def persist_session(state, session_maker, kind: str) -> dict[str, Any]:
    """Persist a finished mapping run + its field mappings to Postgres.

    Args:
        state: The current :class:`GlobalAgentState`.
        session_maker: An async sessionmaker (from :mod:`app.agents.core.deps`).
        kind: Either ``"canonical"`` or ``"projection"``; controls the
            ``destination_type`` recorded and whether
            ``canonical_session_id`` gets backfilled.

    Returns:
        A dict with the newly-created ``session_id`` and (for canonical
        runs) ``canonical_session_id``.
    """
    async with session_maker() as db:
        customer_id = state.customer_id or 1

        dest_type = state.destination_type or ""
        if kind == "canonical":
            dest_type = "canonical"

        source_value = state.source.value if state.source else "salesforce"
        ms = MappingSession(
            customer_id=customer_id,
            source=source_value,
            source_object=state.source_object or "",
            destination_type=dest_type,
            status="completed",
            mapping_kind=kind,
            canonical_session_id=state.canonical_session_id if kind == "projection" else None,
        )
        db.add(ms)
        await db.flush()

        for m in state.mappings or []:
            if not _has_destination(m):
                continue
            assert ms.id is not None  # noqa: S101 — set by flush()
            db.add(
                FieldMapping(
                    session_id=ms.id,
                    source_field=m.source_field,
                    destination_field=m.destination_field,
                    confidence=float(m.confidence or 0.0),
                    status=m.status.value if hasattr(m.status, "value") else str(m.status),
                    reasoning=m.reasoning or "",
                    transformation=m.transformation_needed,
                    validation_status=(
                        m.validation_status.value
                        if hasattr(m.validation_status, "value")
                        else str(m.validation_status)
                    ),
                    validation_notes=list(m.validation_notes or []),
                )
            )

        await db.commit()

    mapping_runs_total.labels(mapping_kind=kind).inc()
    result: dict[str, Any] = {"session_id": ms.id}
    if kind == "canonical":
        result["canonical_session_id"] = ms.id
    return result


# -----------------------------------------------------------------------------
# FeedbackLearningAgent (ported from src/pipeline/feedback_learner.py)
# -----------------------------------------------------------------------------


class FeedbackLearningAgent:
    """Stores embeddings + golden rules for human-approved/corrected mappings."""

    def __init__(
        self,
        settings: _AgentSettingsProxy,
        openai_service: OpenAIService,
        vector_store: VectorStoreService,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Cache settings + service handles + the shared session maker."""
        self.settings = settings
        self.openai_service = openai_service
        self.vector_store = vector_store
        self.session_maker = session_maker

    async def run(self, state):
        """Persist embeddings + golden rules for human-touched mappings."""
        if not state.session_id:
            return state

        async with self.session_maker() as session:
            for mapping in state.mappings:
                if mapping.status not in {MappingStatus.human_approved, MappingStatus.human_corrected}:
                    continue

                statement = select(FieldMapping).where(
                    col(FieldMapping.session_id) == state.session_id,
                    col(FieldMapping.source_field) == mapping.source_field,
                )
                db_mapping = (await session.execute(statement)).scalar_one_or_none()
                if not db_mapping:
                    continue
                assert db_mapping.id is not None  # noqa: S101

                emb_input = f"{mapping.source_field}::{mapping.destination_field or ''}"
                embedding = (await self.openai_service.embed_texts([emb_input]))[0]
                await self.vector_store.upsert_embedding(
                    field_mapping_id=db_mapping.id,
                    embedding=embedding,
                    metadata={
                        "destination_type": state.destination_type,
                        "source_field": mapping.source_field,
                    },
                )

                if mapping.destination_field:
                    await self._upsert_golden_rule(
                        session=session,
                        source_pattern=mapping.source_field.lower(),
                        destination_field=mapping.destination_field,
                        destination_type=state.destination_type,
                    )

            await session.commit()
        return state

    async def _upsert_golden_rule(
        self,
        session: AsyncSession,
        source_pattern: str,
        destination_field: str,
        destination_type: str,
    ) -> None:
        statement = select(GoldenRule).where(
            col(GoldenRule.source_pattern) == source_pattern,
            col(GoldenRule.destination_field) == destination_field,
            col(GoldenRule.destination_type) == destination_type,
        )
        rule = (await session.execute(statement)).scalar_one_or_none()
        if rule:
            rule.occurrence_count += 1
            golden_rule_hits_total.labels(operation="increment").inc()
            return
        session.add(
            GoldenRule(
                source_pattern=source_pattern,
                destination_field=destination_field,
                destination_type=destination_type,
                occurrence_count=1,
            )
        )
        golden_rule_hits_total.labels(operation="create").inc()
