"""funnel_worker sub-graph — Phase 3: funnel design.

Node flow::

    check_funnel_needed
         │
         ├── funnel skipped (no picklists / user declined)
         │        └── funnel_phase_complete=True → END
         │
         └── funnel enabled
                  │
             gather_funnel_stages  ←── HITL: stage table
                  │
             funnel_phase_complete=True → END
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.funnel_worker.tools import (
    check_funnel_needed,
    gather_funnel_stages,
)

_FUNNEL_NODES = ["check_funnel_needed", "gather_funnel_stages"]


def _make_funnel_router(next_phase_entry: str):
    """Return a router that transitions to next_phase_entry when funnel_phase_complete."""

    def _funnel_route_next(state: GlobalAgentState) -> str:
        if state.funnel_phase_complete:
            return next_phase_entry

        if state.funnel_enabled and not state.funnel_stages:
            return "gather_funnel_stages"

        return "check_funnel_needed"

    return _funnel_route_next


def wire_funnel_phase(builder: StateGraph, next_phase_entry: str = END) -> str:
    """Wire funnel nodes into the parent supervisor graph.

    Args:
        builder: The parent StateGraph to add nodes to.
        next_phase_entry: Node name to route to when funnel_phase_complete.

    Returns the entry-point node name.
    """
    builder.add_node("check_funnel_needed", check_funnel_needed)
    builder.add_node("gather_funnel_stages", gather_funnel_stages)

    _funnel_route_next = _make_funnel_router(next_phase_entry)

    _route_targets: dict[str, str] = {
        "check_funnel_needed": "check_funnel_needed",
        "gather_funnel_stages": "gather_funnel_stages",
        next_phase_entry: next_phase_entry,
    }
    if next_phase_entry != END:
        _route_targets[END] = END

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _FUNNEL_NODES:
        builder.add_conditional_edges(node, _funnel_route_next, route_map)

    return "check_funnel_needed"


def build() -> CompiledStateGraph:
    """Compile the funnel_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_funnel_phase(builder))
    return builder.compile(name="funnel_worker")
