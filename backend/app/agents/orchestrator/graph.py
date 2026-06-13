"""Supervisor graph — sequences the 6 worker sub-graphs.

The supervisor is a thin sequencer (no LLM routing in v1). Same worker is
invoked twice in projection runs: once with ``mapping_kind=canonical``
(default), then again with ``mapping_kind=projection`` after the
``prepare_projection`` node flips state.

Two compile entry points:

- :func:`build_studio_graph` — no checkpointer (for ``langgraph dev``).
- :func:`build_app_graph` — Postgres-backed checkpointer (Stage 3 FastAPI mount).

**UI dev mode:** the compiled graph currently runs welcome + intent only.
Restore the full pipeline from git history when UI testing is complete.
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

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.intent_worker.graph import wire_intent_phase
from app.agents.workers.welcome_worker.tools import route_after_welcome, welcome_user


def _build_supervisor() -> StateGraph:
    """Construct the supervisor :class:`StateGraph` (uncompiled).

    Returns a :class:`StateGraph`. Callers compile with the appropriate
    checkpointer.
    """
    g = StateGraph(GlobalAgentState)

    # --- Phase 0: welcome (on chat connect) ---
    g.add_node("welcome", welcome_user)

    # --- Phase 1: intent (flattened — see wire_intent_phase docstring) ---
    intent_entry = wire_intent_phase(g)

    # --- Edges ---
    g.add_edge(START, "welcome")
    g.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent": intent_entry,
            END: END,
        },
    )

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
