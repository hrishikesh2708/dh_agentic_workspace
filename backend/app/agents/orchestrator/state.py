"""The single state object the supervisor + every worker reads and writes.

Replaces crawler_agent's split between ``MappingRouterState`` (TypedDict, used
by the graph layer) and ``MappingGraphState`` (Pydantic, used by pipeline
agents). Everything is now one Pydantic model.

The ``messages`` field uses ``Annotated[list[BaseMessage], add_messages]`` so
LangGraph's standard message reducer still works under Pydantic.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    Field,
)

from app.schemas import (
    DestinationSchema,
    MappingKind,
    ProposedMapping,
    SourceSchema,
    Sources,
)


class GlobalAgentState(BaseModel):
    """Shared LangGraph state for the supervisor and all worker sub-graphs."""

    # --- Conversation channel ---
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # --- Intent phase tracking ---
    intent_phase: str = "idle"
    intent_phase_complete: bool = False
    pending_clarification: str | None = None
    clarifications_asked: list[str] = Field(default_factory=list)

    # --- Intent slots ---
    signal_type: str | None = None
    signal_type_confidence: str | None = None
    source: Sources | None = None
    source_object: str = ""
    destinations: list[str] = Field(default_factory=list)
    available_objects: list[str] = Field(default_factory=list)
    intent_summary: str | None = None

    # --- Connection phase tracking ---
    source_connected: bool = False
    channel_statuses: dict[str, str] = Field(default_factory=dict)
    connection_phase_complete: bool = False

    # --- Mapping phase tracking ---
    required_canonical_keys: list[str] = Field(default_factory=list)
    # Each entry: {canonical_key, field_label, field_hint, field_category, is_pii}
    canonical_field_details: list[dict] = Field(default_factory=list)
    canonical_mapping_approved: bool = False
    resolve_fields_done: bool = False
    mapping_complete_shown: bool = False
    mapping_phase_complete: bool = False
    pipeline_activated: bool = False

    # --- Run mode (synced from destinations) ---
    run_mode: str = "canonical_only"

    # --- Working data ---
    source_schema: SourceSchema | None = None
    destination_schema: DestinationSchema | None = None
    mappings: list[ProposedMapping] = Field(default_factory=list)
    mapping_kind: MappingKind = MappingKind.canonical

    # --- Session + bookkeeping ---
    user_id: int = -1
    username: str = ""
    project_id: Optional[UUID] = None
    session_id: int | None = None
    canonical_session_id: int | None = None
    has_pending_review: bool = False
    canonical_summary_shown: bool = False
    vector_search_destination_type: str | None = None

    # --- Backward compat ---
    @property
    def destination_type(self) -> str:
        """First destination slug; empty when none selected."""
        return self.destinations[0] if self.destinations else ""
