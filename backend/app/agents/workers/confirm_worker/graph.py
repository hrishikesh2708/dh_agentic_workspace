"""confirm_worker sub-graph — Phase 6: token-gated activation confirmation.

Node flow::

    show_confirmation  ←── HITL: summary card + UUID token displayed
         │
    verify_confirmation
         │
         ├── is_confirmed → confirmation_phase_complete=True → END
         └── mismatch     → show_confirmation (new token, loop)
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.confirm_worker.tools import (
    show_confirmation,
    verify_confirmation,
)

_CONFIRM_NODES = ["show_confirmation", "verify_confirmation"]


def _make_confirm_router(next_phase_entry: str):
    """Return a router that transitions to next_phase_entry when confirmation_phase_complete."""

    def _confirm_route_next(state: GlobalAgentState) -> str:
        if state.confirmation_phase_complete:
            return next_phase_entry

        if state.pending_confirm_token is not None:
            return "verify_confirmation"

        return "show_confirmation"

    return _confirm_route_next


def wire_confirm_phase(builder: StateGraph, next_phase_entry: str = END) -> str:
    """Wire confirm nodes into the parent supervisor graph.

    Args:
        builder: The parent StateGraph to add nodes to.
        next_phase_entry: Node to route to when confirmation_phase_complete.

    Returns the entry-point node name.
    """
    builder.add_node("show_confirmation", show_confirmation)
    builder.add_node("verify_confirmation", verify_confirmation)

    confirm_route_next = _make_confirm_router(next_phase_entry)

    _route_targets: dict[str, str] = {
        "show_confirmation": "show_confirmation",
        "verify_confirmation": "verify_confirmation",
        next_phase_entry: next_phase_entry,
    }
    if next_phase_entry != END:
        _route_targets[END] = END

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _CONFIRM_NODES:
        builder.add_conditional_edges(node, confirm_route_next, route_map)

    return "show_confirmation"


def build() -> CompiledStateGraph:
    """Compile the confirm_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_confirm_phase(builder))
    return builder.compile(name="confirm_worker")
