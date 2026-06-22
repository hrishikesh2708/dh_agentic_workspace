"""Shared LangGraph state for the supervisor and all worker sub-graphs.

All phases of the Signals Setup Copilot flow read and write this single model:

  intent → connection → source_object → funnel → mapping → validation → confirm → activate

Design rules
------------
- Every field has a safe default so the graph can be started with
  ``GlobalAgentState()`` and individual workers only touch their own section.
- DB record IDs (UUIDs) are stored so workers don't have to re-query.
- Phase-complete booleans are the canonical routing signals; the supervisor
  reads them to decide which worker to call next.
- ``messages`` uses LangGraph's ``add_messages`` reducer — append-only,
  safe to update from any node.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.schemas import (
    DestinationSchema,
    MappingKind,
    ProposedMapping,
    SourceSchema,
    Sources,
)


class GlobalAgentState(BaseModel):
    """Single source of truth for the entire copilot session."""

    # =========================================================================
    # Conversation channel
    # =========================================================================

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # =========================================================================
    # Session / project bookkeeping
    # =========================================================================

    user_id: int = -1
    username: str = ""
    project_id: Optional[UUID] = None
    # LangGraph thread_id — matches session.id in the DB (varchar, not int)
    session_id: str | None = None

    # =========================================================================
    # Intent phase
    # Populated by: intent_worker
    # =========================================================================

    intent_phase: str = "idle"  # idle | detecting | clarifying | done
    intent_phase_complete: bool = False

    # Clarification loop
    pending_clarification: str | None = None
    clarifications_asked: list[str] = Field(default_factory=list)

    # Resolved intent slots
    signal_type: str | None = None  # e.g. "offline_conversion"
    signal_type_confidence: str | None = None
    source: Sources | None = None  # full source registry row (slug + display_name + metadata)
    destinations: list[str] = Field(default_factory=list)  # dest slugs e.g. ["meta_capi"]
    intent_summary: str | None = None

    # =========================================================================
    # Connection phase
    # Populated by: connection_worker
    # =========================================================================

    # Source
    source_connected: bool = False
    source_connection_id: Optional[UUID] = None  # project_connection.id

    # Destinations keyed by dest slug
    # channel_statuses: slug → "pending" | "connected" | "failed" | "deferred"
    channel_statuses: dict[str, str] = Field(default_factory=dict)
    # destination_connection_ids: slug → project_connection.id (as str)
    destination_connection_ids: dict[str, str] = Field(default_factory=dict)

    connection_phase_complete: bool = False

    # =========================================================================
    # Source object selection
    # Populated by: connection_worker / source_object_worker
    # =========================================================================

    source_object: str = ""  # SF API name e.g. "Opportunity", "Lead"
    available_objects: list[str] = Field(default_factory=list)
    source_module_id: Optional[UUID] = None  # project_source_module.id
    # Raw SF field list fetched from Salesforce — used by funnel + mapping workers
    schema_snapshot: list[dict] = Field(default_factory=list)

    source_object_phase_complete: bool = False

    # =========================================================================
    # Funnel design phase
    # Populated by: funnel_worker
    # =========================================================================

    funnel_enabled: bool = False
    # Picklist field on the SF object used to drive funnel stages
    funnel_trigger_field: str | None = None
    # Picklist values available for stage mapping
    available_stage_values: list[str] = Field(default_factory=list)
    # Resolved funnel stages — each dict matches project_funnel_stage columns:
    # {stage_order, stage_name, trigger_field, trigger_value,
    #  time_field, value_field, per_destination}
    funnel_stages: list[dict] = Field(default_factory=list)

    funnel_phase_complete: bool = False

    # =========================================================================
    # Field mapping phase
    # Populated by: mapping_worker
    # =========================================================================

    # Canonical keys required for selected destinations (loaded from DB)
    required_canonical_keys: list[str] = Field(default_factory=list)
    # Full canonical field metadata for the LLM mapper + UI
    # Each entry: {canonical_key, display_label, hint, category, is_pii,
    #              is_per_stage, allow_constant, accepted_sf_types}
    canonical_field_details: list[dict] = Field(default_factory=list)

    # Proposed SF-field → canonical mappings
    mappings: list[ProposedMapping] = Field(default_factory=list)
    mapping_kind: MappingKind = MappingKind.canonical

    # Tombstones — canonical keys user explicitly said "don't map this"
    # Never auto-suggested again in the same session
    user_unmapped: list[str] = Field(default_factory=list)

    # Destinations the user chose to skip ("set up later")
    # Still in destinations[] but excluded from activation
    deferred_destinations: list[str] = Field(default_factory=list)

    # Phase flags
    resolve_fields_done: bool = False
    canonical_mapping_approved: bool = False
    mapping_complete_shown: bool = False
    canonical_summary_shown: bool = False
    mapping_phase_complete: bool = False

    # =========================================================================
    # Validation phase
    # Populated by: validation_worker
    # =========================================================================

    # Snapshot of mappings at validation time — used for diff if user edits after
    validation_snapshot: list[dict] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)  # hard blockers
    validation_warnings: list[str] = Field(default_factory=list)  # soft warnings
    validation_passed: bool = False

    validation_phase_complete: bool = False

    # =========================================================================
    # Confirmation phase (token-gated)
    # Prevents accidental activation — user must echo back the UUID token
    # Populated by: confirm_worker
    # =========================================================================

    pending_confirm_token: str | None = None  # shown to user in confirm message
    received_confirm_token: str | None = None  # echoed back by user

    confirmation_phase_complete: bool = False

    # =========================================================================
    # Activation phase
    # Populated by: activation_worker
    # =========================================================================

    pipeline_activated: bool = False
    # dest slug → project_integration.id (as str)
    integration_ids: dict[str, str] = Field(default_factory=dict)
    # connector_config.config_version at activation time
    activated_config_version: int | None = None

    # =========================================================================
    # Mid-flow routing
    # Any worker sets this to signal the supervisor to re-route
    # =========================================================================

    # "add_destination" | "change_object" | "edit_mapping" | None
    pending_action: str | None = None

    # =========================================================================
    # Working data (loaded at runtime, not persisted to DB directly)
    # =========================================================================

    source_schema: SourceSchema | None = None
    destination_schema: DestinationSchema | None = None
    run_mode: str = "canonical_only"  # canonical_only | fan_out
    has_pending_review: bool = False
    vector_search_destination_type: str | None = None

    # ── Schema & drift detection ───────────────────────────────────────────────
    raw_sf_fields: list[str] = Field(default_factory=list)
    """Plain list of SF field API names — safe to pass to LLM (no values)."""

    schema_fingerprint: str | None = None
    """SHA-256 of sorted field names+types — used to detect SF schema drift."""

    canonical_superset: list[str] = Field(default_factory=list)
    """Union of all required canonical keys across active destinations."""

    funnel_canonical_slots: list[dict] = Field(default_factory=list)
    """Expanded canonical slots from funnel stage definitions."""

    # ── SF object suggestion ───────────────────────────────────────────────────
    sf_object_candidate: str | None = None
    """LLM-suggested SF object before user confirms."""

    sf_object_confirmed: bool = False
    """True once user explicitly confirmed the object selection."""

    sf_object_reason: str | None = None
    """Why this object was suggested (shown to user)."""

    sf_object_alternatives: list[str] = Field(default_factory=list)
    """Other objects the user could choose instead."""

    # ── Structured clarification ───────────────────────────────────────────────
    open_question_id: str | None = None
    """ID of the pending open question (prevents asking two at once)."""

    open_question_text: str | None = None
    """Text of the pending open question shown to user."""

    open_question_options: list[str] = Field(default_factory=list)
    """Optional constrained answer set for the open question."""

    # ── Config integrity ───────────────────────────────────────────────────────
    confirmed_config_hash: str | None = None
    """SHA-256 of config snapshot taken at confirmation time.
    Cleared if mappings/funnel/destinations change post-confirm."""

    # ── Integration summary (post-activation) ─────────────────────────────────
    integration_summary: dict = Field(default_factory=dict)
    """Summary of activated vs deferred destinations after activation."""

    # ── Progress tracking ─────────────────────────────────────────────────────
    current_phase_index: int = 0
    """0-based index of current phase (0=intent ... 7=activation)."""

    total_phases: int = 8
    """Total number of phases in the setup flow."""

    # =========================================================================
    # Computed helpers
    # =========================================================================

    @property
    def destination_type(self) -> str:
        """First destination slug; empty when none selected."""
        return self.destinations[0] if self.destinations else ""

    @property
    def is_confirmed(self) -> bool:
        """True when the user has echoed back the correct confirmation token."""
        return self.pending_confirm_token is not None and self.pending_confirm_token == self.received_confirm_token

    @property
    def active_destinations(self) -> list[str]:
        """Destinations excluding ones the user deferred."""
        return [d for d in self.destinations if d not in self.deferred_destinations]
