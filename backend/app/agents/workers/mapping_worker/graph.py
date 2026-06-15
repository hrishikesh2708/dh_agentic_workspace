"""mapping_worker sub-graph — flattened into the supervisor graph.

Node flow (within a single turn after connection_phase_complete)::

    fetch_schemas
         │
    run_mapping (MapperAgent: SF fields → canonical keys)
         │
    canonical_mapping  ←── HITL: user reviews/corrects SF → canonical table
         │
    resolve_fields     ←── HITL: conditional, only if required keys unmatched
         │
    mapping_complete   ←── StepCompleteCard (informational, no interrupt)
         │
    activate_confirm   ←── HITL: mock activation
         │
        END

Router (_map_route_next) is called after every node and drives transitions
purely from state — no LLM calls in the router.
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.mapping_worker.tools import (
    activate_confirm,
    canonical_mapping_node,
    fetch_schemas,
    mapping_complete,
    resolve_fields_node,
    run_mapping,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_MAPPING_NODES = [
    "fetch_schemas",
    "run_mapping",
    "canonical_mapping",
    "resolve_fields",
    "mapping_complete",
    "activate_confirm",
]


def _map_route_next(state: GlobalAgentState) -> str:
    """Central router for the mapping phase.

    Called after every mapping node. Drives transitions purely from state.

    Priority order:
    1. Done — pipeline activated or phase complete → END
    2. Schema not loaded → fetch_schemas
    3. No mappings yet → run_mapping
    4. Canonical HITL not approved → canonical_mapping
    5. Required keys unresolved → resolve_fields
    6. Summary not shown → mapping_complete
    7. Activation not done → activate_confirm
    """
    if state.pipeline_activated or state.mapping_phase_complete:
        return END

    if not state.source_schema or not state.required_canonical_keys:
        return "fetch_schemas"

    if not state.mappings:
        return "run_mapping"

    if not state.canonical_mapping_approved:
        return "canonical_mapping"

    # Check if any required canonical keys are still unresolved
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

    return "activate_confirm"


# ---------------------------------------------------------------------------
# Sub-graph builder
# ---------------------------------------------------------------------------


def wire_mapping_phase(builder: StateGraph) -> str:
    """Wire all mapping nodes into the parent supervisor graph.

    All nodes share ``_map_route_next`` as their conditional edge target.
    Returns the entry-point node name so the supervisor can wire its
    incoming edge from the connection phase.
    """
    builder.add_node("fetch_schemas", fetch_schemas)
    builder.add_node("run_mapping", run_mapping)
    builder.add_node("canonical_mapping", canonical_mapping_node)
    builder.add_node("resolve_fields", resolve_fields_node)
    builder.add_node("mapping_complete", mapping_complete)
    builder.add_node("activate_confirm", activate_confirm)

    _route_targets: dict[str, str] = {
        "fetch_schemas": "fetch_schemas",
        "run_mapping": "run_mapping",
        "canonical_mapping": "canonical_mapping",
        "resolve_fields": "resolve_fields",
        "mapping_complete": "mapping_complete",
        "activate_confirm": "activate_confirm",
        END: END,
    }

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _MAPPING_NODES:
        builder.add_conditional_edges(node, _map_route_next, route_map)

    return "fetch_schemas"
