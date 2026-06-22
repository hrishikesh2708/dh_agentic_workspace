"""activation_worker sub-graph — Phase 7: DB activation.

Node flow::

    run_activation  ←── writes all pipeline data to DB
         │
        END  (pipeline_activated=True → supervisor terminates session)
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.activation_worker.tools import run_activation


def _activation_route_next(state: GlobalAgentState) -> str:
    """After run_activation, always END."""
    return END


def wire_activation_phase(builder: StateGraph) -> str:
    """Wire activation node into the parent supervisor graph.

    Returns the entry-point node name.
    """
    builder.add_node("run_activation", run_activation)
    builder.add_conditional_edges(
        "run_activation",
        _activation_route_next,
        {END: END},
    )
    return "run_activation"


def build() -> CompiledStateGraph:
    """Compile the activation_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_activation_phase(builder))
    return builder.compile(name="activation_worker")
