"""welcome_worker sub-graph — single greet node."""

from __future__ import annotations

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.welcome_worker.tools import welcome_user


def build() -> CompiledStateGraph:
    """Compile the welcome_worker sub-graph."""
    builder = StateGraph(GlobalAgentState)
    builder.add_node("welcome_user", welcome_user)
    builder.set_entry_point("welcome_user")
    builder.set_finish_point("welcome_user")
    return builder.compile(name="welcome_worker")
