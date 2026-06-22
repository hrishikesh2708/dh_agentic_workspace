"""validation_worker sub-graph — Phase 5: mapping validation.

Node flow::

    validate_mappings
         │
         ├── validation_passed → END
         │
         └── errors exist
                  │
             show_validation_errors  ←── HITL: user reviews errors
                  │
                  ├── edit_mapping → END (supervisor re-routes to mapping)
                  ├── skip_errors  → END (validation_phase_complete=True)
                  └── retry        → validate_mappings (loop)
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.validation_worker.tools import (
    show_validation_errors,
    validate_mappings,
)

_VALIDATION_NODES = ["validate_mappings", "show_validation_errors"]


def _make_validation_router(next_phase_entry: str, mapping_re_entry: str = END):
    """Return a router for validation that handles forward and back routing.

    Args:
        next_phase_entry: Node to route to when validation_phase_complete.
        mapping_re_entry: Node to route to when pending_action=="edit_mapping".
    """

    def _validation_route_next(state: GlobalAgentState) -> str:
        # Pending action — user chose to edit mapping
        if state.pending_action == "edit_mapping":
            return mapping_re_entry

        if state.validation_phase_complete:
            return next_phase_entry

        if state.validation_passed:
            return next_phase_entry

        if state.validation_errors:
            return "show_validation_errors"

        return "validate_mappings"

    return _validation_route_next


def wire_validation_phase(
    builder: StateGraph,
    next_phase_entry: str = END,
    mapping_re_entry: str = END,
) -> str:
    """Wire validation nodes into the parent supervisor graph.

    Args:
        builder: The parent StateGraph to add nodes to.
        next_phase_entry: Node to route to when validation_phase_complete.
        mapping_re_entry: Node to route to when user wants to edit mapping.

    Returns the entry-point node name.
    """
    builder.add_node("validate_mappings", validate_mappings)
    builder.add_node("show_validation_errors", show_validation_errors)

    validation_route_next = _make_validation_router(next_phase_entry, mapping_re_entry)

    _route_targets: dict[str, str] = {
        "validate_mappings": "validate_mappings",
        "show_validation_errors": "show_validation_errors",
        next_phase_entry: next_phase_entry,
    }
    if mapping_re_entry not in _route_targets:
        _route_targets[mapping_re_entry] = mapping_re_entry
    if END not in _route_targets:
        _route_targets[END] = END

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _VALIDATION_NODES:
        builder.add_conditional_edges(node, validation_route_next, route_map)

    return "validate_mappings"


def build() -> CompiledStateGraph:
    """Compile the validation_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_validation_phase(builder))
    return builder.compile(name="validation_worker")
