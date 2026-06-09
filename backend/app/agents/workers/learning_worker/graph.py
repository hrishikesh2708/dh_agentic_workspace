"""learning_worker sub-graph.

Layout::

    persist → learn → END

The two nodes branch internally on ``state.mapping_kind``:

- ``persist`` writes the mapping session to Postgres and (for projection
  runs) narrates the ``projection.map.confirmed`` event.
- ``learn`` calls :class:`FeedbackLearningAgent.run` which upserts
  embeddings + golden rules for human-touched mappings.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph

from app.agents.core import deps
from app.agents.core.messages import projection_narrative_event
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.learning_worker.tools import persist_session


async def _persist(state: GlobalAgentState) -> dict[str, Any]:
    """Persist the mapping session; branches on ``mapping_kind``."""
    mapping_kind = state.mapping_kind.value

    if mapping_kind == "projection":
        result = await persist_session(state, deps.session_maker, kind="projection")
        result["messages"] = [
            await projection_narrative_event("map", "confirmed", state),
        ]
        return result

    # canonical: persist (auto-persist path already handled in reviewer_worker;
    # this branch is exercised on the human-approved canonical path)
    return await persist_session(state, deps.session_maker, kind="canonical")


async def _learn(state: GlobalAgentState) -> dict[str, Any]:
    """Run :class:`FeedbackLearningAgent` and return the updated mappings."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.learner.run(pipeline_state)
    return {"mappings": result.mappings}


def build() -> CompiledStateGraph:
    """Compile the learning_worker sub-graph."""
    builder = StateGraph(GlobalAgentState)
    builder.add_node("persist", _persist)
    builder.add_node("learn", _learn)
    builder.set_entry_point("persist")
    builder.add_edge("persist", "learn")
    builder.add_edge("learn", END)
    return builder.compile(name="learning_worker")
