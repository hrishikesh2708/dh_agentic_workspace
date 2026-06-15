"""Supervisor graph — sequences the worker sub-graphs."""

from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.connection_worker.graph import wire_connection_phase
from app.agents.workers.intent_worker.graph import route_after_intent, wire_intent_phase
from app.agents.workers.mapping_worker.graph import wire_mapping_phase
from app.agents.workers.welcome_worker.tools import route_after_welcome, welcome_user


def _build_supervisor() -> StateGraph:
    g = StateGraph(GlobalAgentState)

    # Phase 0: welcome
    g.add_node("welcome", welcome_user)

    # Phase 1: intent (flattened)
    intent_entry = wire_intent_phase(g)

    # Phase 3: mapping (registered first so the entry node name is known
    # before wire_connection_phase wires its exit route)
    mapping_entry = wire_mapping_phase(g)

    # Phase 2: connection (flattened — routes directly to mapping_entry when done)
    connection_entry = wire_connection_phase(g, next_phase_entry=mapping_entry)

    # Edges
    g.add_edge(START, "welcome")
    g.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent": intent_entry,
            "handle_clarification": "handle_clarification",
            "handle_confirmation": "handle_confirmation",
            END: END,
        },
    )

    # Intent complete → connection phase
    g.add_conditional_edges(
        "handle_confirmation",
        route_after_intent,
        {"connection_phase": connection_entry, END: END},
    )
    # Connection → mapping is wired internally by wire_connection_phase via
    # _make_conn_router(next_phase_entry=mapping_entry). No explicit edge needed.

    return g


def build_studio_graph() -> CompiledStateGraph:
    """Compile the supervisor graph without a checkpointer (``langgraph dev``)."""
    return _build_supervisor().compile(name="datahash_agent")


def build_app_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Compile the supervisor graph with an optional Postgres checkpointer."""
    return _build_supervisor().compile(
        checkpointer=checkpointer,
        name="datahash_agent",
    )
