"""Named, testable routing guard functions for the supervisor graph.

Each function takes GlobalAgentState and returns bool.
Import these into graph.py instead of inlining lambdas on conditional edges.
"""

# ruff: noqa: D103

from __future__ import annotations

from app.agents.orchestrator.state import GlobalAgentState


# ── Phase completion guards ────────────────────────────────────────────────


def intent_complete(state: GlobalAgentState) -> bool:
    return bool(state.intent_phase_complete)


def connection_complete(state: GlobalAgentState) -> bool:
    return bool(state.connection_phase_complete)


def source_object_complete(state: GlobalAgentState) -> bool:
    return bool(state.source_object_phase_complete)


def funnel_complete(state: GlobalAgentState) -> bool:
    return bool(state.funnel_phase_complete)


def mapping_complete(state: GlobalAgentState) -> bool:
    return bool(state.mapping_phase_complete)


def validation_complete(state: GlobalAgentState) -> bool:
    return bool(state.validation_phase_complete)


def confirmation_complete(state: GlobalAgentState) -> bool:
    return bool(state.confirmation_phase_complete)


def pipeline_activated(state: GlobalAgentState) -> bool:
    return bool(state.pipeline_activated)


# ── Validation sub-routing ────────────────────────────────────────────────


def validation_has_errors(state: GlobalAgentState) -> bool:
    return bool(state.validation_errors)


def validation_passed(state: GlobalAgentState) -> bool:
    return bool(state.validation_passed)


def confirmation_is_valid(state: GlobalAgentState) -> bool:
    return bool(state.is_confirmed)


# ── Mid-flow guards ────────────────────────────────────────────────────────


def has_pending_action(state: GlobalAgentState) -> bool:
    return state.pending_action is not None


def mapping_needs_review(state: GlobalAgentState) -> bool:
    return bool(getattr(state, "has_pending_review", False))


def funnel_is_enabled(state: GlobalAgentState) -> bool:
    return bool(getattr(state, "funnel_enabled", False))


def config_hash_valid(state: GlobalAgentState) -> bool:
    """True if the confirmed config hash is still valid (no edits post-confirm)."""
    return state.confirmed_config_hash is not None


# ── Source / destination ─────────────────────────────────────────────────


def source_is_connected(state: GlobalAgentState) -> bool:
    return bool(getattr(state, "source_connected", False))


def all_channels_settled(state: GlobalAgentState) -> bool:
    """True if every selected destination is either connected or deferred."""
    active = set(getattr(state, "active_destinations", []) or [])
    deferred = set(getattr(state, "deferred_destinations", []) or [])
    channel_statuses = getattr(state, "channel_statuses", {}) or {}
    connected = {d for d, s in channel_statuses.items() if s == "connected"}
    return active.issubset(connected | deferred)
