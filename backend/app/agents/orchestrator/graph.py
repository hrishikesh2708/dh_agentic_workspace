"""Supervisor graph — sequences the 5 worker sub-graphs.

The supervisor is a thin sequencer (no LLM routing in v1). Same worker is
invoked twice in projection runs: once with ``mapping_kind=canonical``
(default), then again with ``mapping_kind=projection`` after the
``prepare_projection`` node flips state.

Two compile entry points:

- :func:`build_studio_graph` — no checkpointer (for ``langgraph dev``).
- :func:`build_app_graph` — Postgres-backed checkpointer (Stage 3 FastAPI mount).
"""

from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.router_nodes import (
    done_summary_node,
    prepare_projection_node,
    route_post_canonical_learning,
    route_post_canonical_reviewer,
    route_post_projection_reviewer,
)
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.intent_worker.graph import build as build_intent
from app.agents.workers.learning_worker.graph import build as build_learning
from app.agents.workers.mapper_worker.graph import build as build_mapper
from app.agents.workers.reviewer_worker.graph import build as build_reviewer
from app.agents.workers.schema_worker.graph import build as build_schema


def _build_supervisor() -> StateGraph:
    """Construct the supervisor :class:`StateGraph` (uncompiled).

    Returns a :class:`StateGraph`. Callers compile with the appropriate
    checkpointer.
    """
    # Build each worker once — same compiled sub-graph is reused under
    # canonical and projection node names.
    intent_g = build_intent()
    schema_g = build_schema()
    mapper_g = build_mapper()
    reviewer_g = build_reviewer()
    learning_g = build_learning()

    g = StateGraph(GlobalAgentState)

    # --- Phase 1: intent ---
    g.add_node("intent", intent_g)

    # --- Phase 2: canonical chain ---
    g.add_node("schema_canonical", schema_g)
    g.add_node("mapper_canonical", mapper_g)
    g.add_node("reviewer_canonical", reviewer_g)
    g.add_node("learning_canonical", learning_g)

    # --- Phase 3: projection chain (optional) ---
    g.add_node("prepare_projection", prepare_projection_node)
    g.add_node("schema_projection", schema_g)
    g.add_node("mapper_projection", mapper_g)
    g.add_node("reviewer_projection", reviewer_g)
    g.add_node("learning_projection", learning_g)

    # --- Terminal ---
    g.add_node("done_summary", done_summary_node)

    # --- Edges ---
    g.add_edge(START, "intent")
    g.add_edge("intent", "schema_canonical")
    g.add_edge("schema_canonical", "mapper_canonical")
    g.add_edge("mapper_canonical", "reviewer_canonical")

    g.add_conditional_edges(
        "reviewer_canonical",
        route_post_canonical_reviewer,
        {
            "learning_canonical": "learning_canonical",
            "prepare_projection": "prepare_projection",
            "done_summary": "done_summary",
        },
    )
    g.add_conditional_edges(
        "learning_canonical",
        route_post_canonical_learning,
        {
            "prepare_projection": "prepare_projection",
            "done_summary": "done_summary",
        },
    )

    g.add_edge("prepare_projection", "schema_projection")
    g.add_edge("schema_projection", "mapper_projection")
    g.add_edge("mapper_projection", "reviewer_projection")

    g.add_conditional_edges(
        "reviewer_projection",
        route_post_projection_reviewer,
        {
            "learning_projection": "learning_projection",
            "done_summary": "done_summary",
        },
    )
    g.add_edge("learning_projection", "done_summary")
    g.add_edge("done_summary", END)

    return g


def build_studio_graph() -> CompiledStateGraph:
    """Compile the supervisor without a checkpointer (for LangGraph Studio).

    The ``langgraph dev`` CLI injects its own in-memory checkpointer at
    runtime, so we leave that slot unfilled here.
    """
    return _build_supervisor().compile(name="datahash_agent")


def build_app_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Compile the supervisor for the FastAPI app (Stage 3).

    Args:
        checkpointer: Async Postgres saver from the FastAPI lifespan. ``None``
            is permitted so the app boots in degraded mode if Postgres is
            unavailable in production.

    Returns:
        The compiled supervisor :class:`CompiledStateGraph`.
    """
    return _build_supervisor().compile(
        checkpointer=checkpointer,
        name="datahash_agent",
    )
