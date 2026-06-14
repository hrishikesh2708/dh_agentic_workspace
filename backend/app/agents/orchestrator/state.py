"""The single state object the supervisor + every worker reads and writes.

Replaces crawler_agent's split between ``MappingRouterState`` (TypedDict, used
by the graph layer) and ``MappingGraphState`` (Pydantic, used by pipeline
agents). Everything is now one Pydantic model.

The ``messages`` field uses ``Annotated[list[BaseMessage], add_messages]`` so
LangGraph's standard message reducer still works under Pydantic.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.agent.types import (
    DestinationSchema,
    MappingKind,
    ProposedMapping,
    SourceSchema,
    Sources,
)


class GlobalAgentState(BaseModel):
    """Unified state for the supervisor + worker sub-graphs.

    Naming preserved from crawler_agent (`customer_id` / `session_id` as
    ``int``) so the pipeline + persistence code ports verbatim. They'll be
    reconciled with the framework's ``user_id`` / ``Session.id`` in Stage 2
    when the DB models land.
    """

    # --- Conversation channel (LangGraph reducer) ---
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # --- Run mode + intent (Phase 1: intent_worker) ---
    run_mode: str = "canonical_only"
    source: Sources | None = None
    source_object: str = ""
    destination_type: str = ""
    available_objects: list[str] = Field(default_factory=list)

    # --- Working data (Phase 2/3: schema/mapper/reviewer/learning) ---
    source_schema: SourceSchema | None = None
    destination_schema: DestinationSchema | None = None
    mappings: list[ProposedMapping] = Field(default_factory=list)
    mapping_kind: MappingKind = MappingKind.canonical

    # --- Session + bookkeeping ---
    user_id: int = -1
    username: str = ""
    session_id: int | None = None
    canonical_session_id: int | None = None
    has_pending_review: bool = False
    canonical_summary_shown: bool = False
    vector_search_destination_type: str | None = None
