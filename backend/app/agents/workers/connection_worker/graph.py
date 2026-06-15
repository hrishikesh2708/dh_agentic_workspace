"""connection_worker sub-graph — Phase 2: connection checks + object selection."""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.core.intent_validation import normalize_optional_str, source_connector_id
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.connection_worker.tools import (
    _SUPPORTED_OBJECT_SOURCES,
    check_channel_connections,
    check_source_connection,
    gather_object,
)


def _make_conn_router(next_phase_entry: str):
    """Return a _conn_route_next closure that transitions to next_phase_entry when done."""

    def _conn_route_next(state: GlobalAgentState) -> str:
        if state.connection_phase_complete:
            return next_phase_entry
        if not state.source_connected:
            return "check_source_connection"
        source_id = source_connector_id(state.source) or ""
        if source_id.lower() in _SUPPORTED_OBJECT_SOURCES:
            if not normalize_optional_str(state.source_object):
                return "gather_object"
        if not state.channel_statuses:
            return "check_channel_connections"
        return next_phase_entry  # all checks passed but flag not yet set — safe fallback

    return _conn_route_next


def wire_connection_phase(builder: StateGraph, next_phase_entry: str = END) -> str:
    """Wire connection nodes into the supervisor graph.

    Args:
        builder: The parent StateGraph to add nodes to.
        next_phase_entry: Node name to route to when connection_phase_complete.
                          Defaults to END (terminates the graph turn).
    """
    builder.add_node("check_source_connection", check_source_connection)
    builder.add_node("gather_object", gather_object)
    builder.add_node("check_channel_connections", check_channel_connections)

    _conn_route_next = _make_conn_router(next_phase_entry)

    _route_targets: dict[str, str] = {
        "check_source_connection": "check_source_connection",
        "gather_object": "gather_object",
        "check_channel_connections": "check_channel_connections",
        next_phase_entry: next_phase_entry,
    }
    # Always include END in the map so LangGraph can resolve it
    if next_phase_entry != END:
        _route_targets[END] = END

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in ["check_source_connection", "gather_object", "check_channel_connections"]:
        builder.add_conditional_edges(node, _conn_route_next, route_map)

    return "check_source_connection"


def build() -> CompiledStateGraph:
    """Compile the connection_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_connection_phase(builder))
    return builder.compile(name="connection_worker")
