"""mapper_worker sub-graph.

Single node — wraps :class:`MapperAgent.run`. The same worker is invoked
twice in projection mode (once for canonical, once for projection); the
state's ``vector_search_destination_type`` controls which past mappings are
retrieved for examples.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph

from app.agents.core import deps
from app.agents.orchestrator.state import GlobalAgentState


async def _map(state: GlobalAgentState) -> dict[str, Any]:
    """Run the mapper and return the updated mappings."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.mapper.run(pipeline_state)
    return {"mappings": result.mappings}


def build() -> CompiledStateGraph:
    """Compile the mapper_worker sub-graph."""
    builder = StateGraph(GlobalAgentState)
    builder.add_node("map", _map)
    builder.set_entry_point("map")
    builder.add_edge("map", END)
    return builder.compile(name="mapper_worker")
