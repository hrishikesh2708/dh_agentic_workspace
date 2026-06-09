"""schema_worker sub-graph.

Layout:

- entry: ``schema_router`` (decides mode based on ``state.run_mode``)
- canonical mode (fan-out):
   - ``extract_source``  (Salesforce describe)
   - ``load_internal``   (canonical YAML)
- projection mode:
   - ``setup_projection`` (rewires state for projection)
   - ``load_destination`` (destination YAML)

The supervisor calls this worker once per stage (canonical, then projection if
applicable).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.agents.core import deps
from app.agents.core.messages import canonical_narrative_event
from app.agents.orchestrator.state import GlobalAgentState
from app.schemas.agent.types import (
    DestinationSchema,
    SourceField,
    SourceSchema,
)


# -----------------------------------------------------------------------------
# Node functions (operate on GlobalAgentState)
# -----------------------------------------------------------------------------


async def _route_by_mode(state: GlobalAgentState) -> Command:
    """Entry node — dispatches to canonical fan-out or projection setup.

    Also emits a 'bridge in_progress' narration message when entering the
    canonical phase from a projection-mode run (mirrors crawler_agent's
    ``canonical_fanout`` node).
    """
    messages: list[Any] = []
    if state.run_mode == "projection":
        # Original code emitted this on canonical_fanout when run_mode==projection.
        # That ran once at the start; preserve the behaviour.
        messages.append(await canonical_narrative_event("bridge", "in_progress", state))

    update: dict[str, Any] = {"messages": messages} if messages else {}
    if state.mapping_kind.value == "projection":
        return Command(update=update, goto="setup_projection")
    return Command(update=update, goto="canonical_fanout")


async def _canonical_fanout(state: GlobalAgentState) -> Command:
    """Tiny dispatcher that fans out to ``extract_source`` and ``load_internal`` in parallel."""
    # No state mutation — just dispatches.
    _ = state  # silence unused-arg lint
    return Command(goto=["extract_source", "load_internal"])


async def _extract_source(state: GlobalAgentState) -> dict[str, Any]:
    """Call SchemaExtractorAgent → updates ``source_schema``."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.schema_extractor.run(pipeline_state)
    return {"source_schema": result.source_schema}


async def _load_internal(state: GlobalAgentState) -> dict[str, Any]:
    """Call InternalSchemaAgent → loads canonical schema as the destination."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.internal_schema.run(pipeline_state)
    return {
        "destination_schema": result.destination_schema,
        "destination_type": result.destination_type,
        "vector_search_destination_type": result.vector_search_destination_type,
    }


async def _setup_projection(state: GlobalAgentState) -> dict[str, Any]:
    """Rewire state for projection: canonical output becomes the new source.

    Ported from ``graph/nodes/projection.py::setup_projection``. The
    destination schema (canonical we just produced) is recast as a source
    schema; the new destination_schema will be loaded by ``_load_destination``.
    """
    canonical_dest = state.destination_schema
    source_schema_for_proj: SourceSchema | None = None

    if canonical_dest:
        if isinstance(canonical_dest, dict):
            dest_obj = DestinationSchema.model_validate(canonical_dest)
        else:
            dest_obj = canonical_dest
        source_schema_for_proj = SourceSchema(
            object_name="canonical",
            fields=[
                SourceField(
                    name=f.name,
                    label=f.name,
                    type=f.type,
                    description=f.description or "",
                )
                for f in dest_obj.fields
            ],
        )

    return {
        "source_schema": source_schema_for_proj,
        "destination_schema": None,
        "mappings": [],
        "has_pending_review": False,
        "canonical_session_id": state.session_id,
        "session_id": None,
    }


async def _load_destination(state: GlobalAgentState) -> dict[str, Any]:
    """Call SchemaRegistryAgent → loads the projection target's schema."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.schema_registry.run(pipeline_state)
    return {
        "destination_schema": result.destination_schema,
        "vector_search_destination_type": state.destination_type,
    }


# -----------------------------------------------------------------------------
# Sub-graph builder
# -----------------------------------------------------------------------------


def build() -> CompiledStateGraph:
    """Compile the schema_worker sub-graph.

    Returns:
        A :class:`CompiledStateGraph` ready to be added as a node in the
        supervisor.
    """
    builder = StateGraph(GlobalAgentState)
    builder.add_node("route", _route_by_mode, destinations=("canonical_fanout", "setup_projection"))
    builder.add_node("canonical_fanout", _canonical_fanout, destinations=("extract_source", "load_internal"))
    builder.add_node("extract_source", _extract_source)
    builder.add_node("load_internal", _load_internal)
    builder.add_node("setup_projection", _setup_projection)
    builder.add_node("load_destination", _load_destination)

    builder.set_entry_point("route")
    builder.add_edge("extract_source", END)
    builder.add_edge("load_internal", END)
    builder.add_edge("setup_projection", "load_destination")
    builder.add_edge("load_destination", END)

    return builder.compile(name="schema_worker")
