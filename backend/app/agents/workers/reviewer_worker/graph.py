"""reviewer_worker sub-graph.

Layout::

    validate → score → (review | auto_persist) → END

``score`` writes ``state.has_pending_review``. The conditional edge after
``score`` routes to the HITL ``review`` node if any mapping needs human
input, otherwise to ``auto_persist``. ``review`` raises a LangGraph
``interrupt`` carrying the ``mapping_review`` payload — on resume the
client's response is applied via :func:`apply_review_response`.

The same sub-graph is used for both the **canonical** and **projection**
stages; ``state.mapping_kind`` selects narration + payload shapes inside
the nodes.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.agents.core import deps
from app.agents.core.messages import (
    canonical_narrative_event,
    canonical_stage_complete_message,
    destination_field_options,
    narrative_message,
    projection_narrative_event,
)
from app.core.metrics import hitl_interruptions_total
from app.agents.core.narratives import CANONICAL_LABEL
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.reviewer_worker.tools import (
    apply_review_response,
    build_mapping_review_interrupt,
    build_mapping_summary,
    expand_mappings_for_review,
    persist_session,
)
from app.schemas.agent.types import (
    MappingKind,
    ProposedMapping,
)


def _dicts_to_mappings(rows: list[dict]) -> list[ProposedMapping]:
    """Validate the post-review dicts back into ``ProposedMapping`` objects."""
    return [ProposedMapping.model_validate(r) for r in rows]


# -----------------------------------------------------------------------------
# Node functions
# -----------------------------------------------------------------------------


async def _validate(state: GlobalAgentState) -> dict[str, Any]:
    """Run :class:`ValidatorAgent` and update ``state.mappings``."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.validator.run(pipeline_state)
    return {"mappings": result.mappings}


async def _score(state: GlobalAgentState) -> dict[str, Any]:
    """Run :class:`ConfidenceScorerAgent` and set ``has_pending_review``."""
    pipeline_state = state.model_copy(deep=True)
    result = await deps.scorer.run(pipeline_state)
    return {
        "mappings": result.mappings,
        "has_pending_review": result.has_pending_review,
    }


async def _review(state: GlobalAgentState) -> dict[str, Any]:
    """HITL review — pause for client decisions and apply the response."""
    full_mappings = expand_mappings_for_review(state)
    mapping_kind = state.mapping_kind.value
    source_object = state.source_object or ("canonical" if mapping_kind == "projection" else "")
    destination_type = "canonical" if mapping_kind == "canonical" else (state.destination_type or "")

    payload = build_mapping_review_interrupt(
        mapping_kind=mapping_kind,
        source_object=source_object,
        destination_type=destination_type,
        mappings=full_mappings,
        destination_fields=destination_field_options(state),
        mapping_summary=build_mapping_summary(full_mappings),
    )
    hitl_interruptions_total.labels(interrupt_type="mapping_review").inc()
    response: Any = interrupt(payload)

    updated_dicts = apply_review_response(full_mappings, response)
    updated = _dicts_to_mappings(updated_dicts)
    approved = isinstance(response, dict) and response.get("approved", True)

    if not approved:
        if mapping_kind == "canonical":
            cancel_msg = narrative_message(
                "canonical",
                "cancelled",
                "message",
                labels={"canonical_label": CANONICAL_LABEL},
            )
        else:
            cancel_msg = narrative_message("projection", "cancelled", "message")
        return {
            "messages": [cancel_msg],
            "mappings": updated,
        }

    if mapping_kind == "canonical":
        # Build a working state copy so the stage_complete message uses the
        # post-review mappings (its payload reads from the list arg, not state).
        return {
            "messages": [
                await canonical_narrative_event("map", "confirmed", state),
                canonical_stage_complete_message(state, updated_dicts),
            ],
            "mappings": updated,
            "canonical_summary_shown": True,
        }

    # projection: no stage_complete on this path (done_summary handles it)
    return {"mappings": updated}


async def _auto_persist(state: GlobalAgentState) -> dict[str, Any]:
    """Auto-approve path: persist immediately, narrate stage completion.

    Mirrors crawler_agent's ``canonical_auto_persist``. For projection runs
    we skip persistence and narrate the map-confirmed event only.
    """
    mapping_kind = state.mapping_kind.value
    if mapping_kind == "canonical":
        result = await persist_session(state, deps.session_maker, kind="canonical")
        if state.run_mode == "projection":
            result["canonical_summary_shown"] = True
        mappings_for_payload = [m.model_dump() for m in state.mappings]
        result["messages"] = [
            await canonical_narrative_event("map", "confirmed", state),
            canonical_stage_complete_message(
                state,
                mappings_for_payload,
                session_id=result.get("session_id"),
            ),
        ]
        return result

    # projection auto-approve: narrate only.
    return {
        "messages": [
            await projection_narrative_event("map", "confirmed", state),
        ],
    }


# -----------------------------------------------------------------------------
# Conditional router
# -----------------------------------------------------------------------------


def _route_after_score(state: GlobalAgentState) -> str:
    """Branch on ``has_pending_review`` after the scoring node."""
    if state.has_pending_review:
        return "review"
    return "auto_persist"


# -----------------------------------------------------------------------------
# Sub-graph builder
# -----------------------------------------------------------------------------


def build() -> CompiledStateGraph:
    """Compile the reviewer_worker sub-graph."""
    builder = StateGraph(GlobalAgentState)
    builder.add_node("validate", _validate)
    builder.add_node("score", _score)
    builder.add_node("review", _review)
    builder.add_node("auto_persist", _auto_persist)

    builder.set_entry_point("validate")
    builder.add_edge("validate", "score")
    builder.add_conditional_edges(
        "score",
        _route_after_score,
        {
            "review": "review",
            "auto_persist": "auto_persist",
        },
    )
    builder.add_edge("review", END)
    builder.add_edge("auto_persist", END)

    # MappingKind is unused at module scope but required to keep state schema deps clear.
    _ = MappingKind
    return builder.compile(name="reviewer_worker")
