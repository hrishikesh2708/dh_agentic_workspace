"""mapping_worker sub-graph — flattened into the supervisor graph.

Node flow (within a single turn after funnel_phase_complete)::

    fetch_schemas
         │
    run_mapping (MapperAgent: SF fields → canonical keys)
         │
    canonical_mapping  ←── HITL: user reviews/corrects SF → canonical table
         │
    resolve_fields     ←── HITL: conditional, only if required keys unmatched
         │
    mapping_complete   ←── StepCompleteCard; sets mapping_phase_complete=True
         │
    next_phase_entry   →  validation_worker

Router is created by _make_map_router and called after every mapping node.
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.mapping_worker.tools import (
    canonical_mapping_node,
    fetch_schemas,
    mapping_complete,
    resolve_fields_node,
    run_mapping,
)

_MAPPING_NODES = [
    "fetch_schemas",
    "run_mapping",
    "canonical_mapping",
    "resolve_fields",
    "mapping_complete",
]


def _make_map_router(next_phase_entry: str):
    """Return a router that transitions to next_phase_entry when mapping_phase_complete."""

    def _map_route_next(state: GlobalAgentState) -> str:
        if state.mapping_phase_complete:
            return next_phase_entry

        if not state.source_schema or not state.required_canonical_keys:
            return "fetch_schemas"

        if not state.mappings:
            return "run_mapping"

        if not state.canonical_mapping_approved:
            return "canonical_mapping"

        already_mapped = {
            m.destination_field
            for m in state.mappings
            if m.destination_field and m.source_field and m.status not in ("unmatched", "not_proposed")
        }
        unresolved = [k for k in state.required_canonical_keys if k not in already_mapped]
        if unresolved and not state.resolve_fields_done:
            return "resolve_fields"

        if not state.mapping_complete_shown:
            return "mapping_complete"

        return next_phase_entry

    return _map_route_next


def wire_mapping_phase(builder: StateGraph, next_phase_entry: str = END) -> str:
    """Wire all mapping nodes into the parent supervisor graph.

    Args:
        builder: The parent StateGraph to add nodes to.
        next_phase_entry: Node name to route to when mapping_phase_complete.
                          Defaults to END.

    Returns the entry-point node name.
    """
    builder.add_node("fetch_schemas", fetch_schemas)
    builder.add_node("run_mapping", run_mapping)
    builder.add_node("canonical_mapping", canonical_mapping_node)
    builder.add_node("resolve_fields", resolve_fields_node)
    builder.add_node("mapping_complete", mapping_complete)

    map_route_next = _make_map_router(next_phase_entry)

    _route_targets: dict[str, str] = {
        "fetch_schemas": "fetch_schemas",
        "run_mapping": "run_mapping",
        "canonical_mapping": "canonical_mapping",
        "resolve_fields": "resolve_fields",
        "mapping_complete": "mapping_complete",
        next_phase_entry: next_phase_entry,
    }
    if next_phase_entry != END:
        _route_targets[END] = END

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _MAPPING_NODES:
        builder.add_conditional_edges(node, map_route_next, route_map)

    return "fetch_schemas"
