"""Supervisor-level router functions + leaf nodes.

Conditional edges in LangGraph can return any node name in the graph, so we
encode the run-mode and HITL skip logic here rather than scattering it across
worker sub-graphs.
"""

from __future__ import annotations

from typing import Any

from app.agents.messages import mapping_complete_message
from app.agents.orchestrator.state import GlobalAgentState
from app.schemas import MappingKind


# -----------------------------------------------------------------------------
# Conditional edge functions
# -----------------------------------------------------------------------------


def route_post_canonical_reviewer(state: GlobalAgentState) -> str:
    """Decide what runs after the canonical reviewer finishes.

    - If the reviewer triggered a HITL flow (``has_pending_review`` was set
      by the scorer), the human-approved/corrected mappings still need to be
      persisted + learned from → ``learning_canonical``.
    - Otherwise the reviewer's ``auto_persist`` node already wrote the
      session, so we skip ``learning`` and go straight to the post-canonical
      decision.
    """
    if state.has_pending_review:
        return "learning_canonical"
    if state.run_mode == "projection":
        return "prepare_projection"
    return "done_summary"


def route_post_canonical_learning(state: GlobalAgentState) -> str:
    """After learning the canonical mappings — projection or done?"""
    if state.run_mode == "projection":
        return "prepare_projection"
    return "done_summary"


def route_post_projection_reviewer(state: GlobalAgentState) -> str:
    """After the projection reviewer — learn (if HITL happened) or finish."""
    if state.has_pending_review:
        return "learning_projection"
    return "done_summary"


# -----------------------------------------------------------------------------
# Node functions
# -----------------------------------------------------------------------------


async def prepare_projection_node(state: GlobalAgentState) -> dict[str, Any]:
    """Flip state into projection mode before the second schema/mapper/reviewer pass.

    Flips ``mapping_kind`` to projection and resets the per-stage HITL toggle.
    """
    _ = state  # state read happens downstream; nothing to read here
    return {
        "mapping_kind": MappingKind.projection,
        "has_pending_review": False,
    }


async def done_summary_node(state: GlobalAgentState) -> dict[str, Any]:
    """Final node — emits the ``mapping_complete`` payload (ported from terminal.py).

    Skips the message if the canonical-only run already emitted its
    stage_complete via the auto_persist path (avoiding duplicate UI events).
    """
    if state.run_mode == "canonical_only" and state.canonical_summary_shown:
        return {}
    return {"messages": [await mapping_complete_message(state)]}
