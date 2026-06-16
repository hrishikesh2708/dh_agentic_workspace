r"""intent_worker sub-graph — Layers 1-6.

All intent nodes are flattened directly into the supervisor graph (not nested
as a compiled subgraph). Flattening keeps HITL interrupts and AIMessages on the
supervisor so CopilotKit/AG-UI can stream them to the UI correctly.

Turn-based routing pattern
--------------------------
``handle_clarification`` and ``handle_confirmation`` read ``last_user_text`` to
process the user's reply. They must therefore only run at the *start* of the
turn in which that reply arrives — never in the same turn that generated the
question. ``_route_next`` returns END for the "clarifying" and "confirming"
phases; ``route_after_welcome`` in welcome_worker detects those phases and
bypasses ``parse_initial_intent``, routing directly to the handler on the next
user turn.

Node flow (within a single turn)::

    parse_initial_intent
            │
            ▼
        [_route_next]
       /    |    \
      ▼     ▼     ▼
  gather_ gather_ gather_    END (clarifying/confirming — wait for next turn)
  source  object  dests
      \     |     /
       ▼    ▼    ▼
        [_route_next]
              │
              ▼
        confirm_intent   ──►  END (confirming — wait for next turn)
              │
        [_route_next]
              │
             END  →  handoff to connection phase (future)

Cross-turn routing (via route_after_welcome)::

    User reply arrives
          │
    route_after_welcome detects intent_phase
          │
          ├── "clarifying"  ──►  handle_clarification  ──►  [_route_next]
          ├── "confirming"  ──►  handle_confirmation   ──►  [_route_next]
          └── anything else ──►  parse_initial_intent  ──►  [_route_next]
"""

from __future__ import annotations

from typing import Hashable, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.core import deps
from app.agents.core.intent_validation import (
    is_valid_source,
    normalize_optional_str,
    source_connector_id,
)
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.intent_worker.tools import (
    confirm_intent,
    gather_destinations,
    gather_source,
    handle_clarification,
    handle_confirmation,
    parse_initial_intent,
)


def _has_valid_destinations(destinations: list[str], valid_ids: set[str]) -> bool:
    """At least one destination must be in the enabled set."""
    if not destinations:
        return False
    return any(d.lower() in valid_ids for d in destinations)


async def _route_next(state: GlobalAgentState) -> str:
    """Central router for the intent phase.

    Called after every node in the intent subgraph. Determines the next step
    based purely on state — no LLM calls.

    Priority order:
    1. Phase-based routing (clarifying / confirming / complete) — overrides all
    2. Slot-based routing — signal_type → source → destinations
    3. Confirmation — all slots filled, needs user sign-off
    4. Complete — hand off to connection phase (returns END for now)
    """
    # --- Priority 1: Phase-based routing ----------------------------------------
    if state.intent_phase == "complete":
        return END

    # "clarifying" and "confirming" both need new user input before the
    # corresponding handler node can run meaningfully. End this turn here;
    # route_after_welcome will route directly to the right handler on the
    # next user message (so it sees the actual reply, not the original message).
    if state.intent_phase in ("clarifying", "confirming"):
        return END

    # --- Priority 2: Slot validation (dependency order) -------------------------
    # Signal type first — establishes *what* the user is trying to do and
    # contextualises source/destination options shown in subsequent steps.
    if not state.signal_type:
        return "handle_clarification"

    # Source second — *where* the data lives.
    source_id = source_connector_id(state.source)
    source = normalize_optional_str(source_id) or ""
    valid_source_ids = await deps.connector_schema.enabled_source_ids()

    if not is_valid_source(source, valid_source_ids):
        return "gather_source"

    # Destinations last — *where* the data should go.
    valid_dest_ids = await deps.connector_schema.enabled_destination_ids()
    if not _has_valid_destinations(state.destinations, valid_dest_ids):
        return "gather_destinations"

    # --- Priority 3: Confirmation ------------------------------------------------
    if not state.intent_phase_complete and state.intent_phase != "confirming":
        return "confirm_intent"

    # --- Priority 4: Complete ----------------------------------------------------
    return END


def route_after_intent(state: GlobalAgentState) -> str:
    """Route from welcome confirmation into the connection phase when intent is complete."""
    if state.intent_phase_complete:
        return "connection_phase"
    return END


def wire_intent_phase(builder: StateGraph) -> str:
    """Wire all intent nodes into the parent supervisor graph.

    Registers seven nodes (Layers 1-5) and connects them all to the central
    ``_route_next`` router. Returns the entry-point node name so the supervisor
    can wire its own incoming edge.

    Changes vs original:
    - Added: ``gather_destinations`` (multi-select, replaces ``gather_destination``)
    - Added: ``handle_clarification`` (free-text clarification loop, Layer 2)
    - Added: ``confirm_intent`` + ``handle_confirmation`` (confirmation pair, Layer 5)
    - Removed: ``gather_destination`` (single-select, superseded)
    """
    # --- Register nodes ---------------------------------------------------------
    builder.add_node("parse_initial_intent", parse_initial_intent)
    builder.add_node("gather_source", gather_source)
    builder.add_node("gather_destinations", gather_destinations)
    builder.add_node("handle_clarification", handle_clarification)
    builder.add_node("confirm_intent", confirm_intent)
    builder.add_node("handle_confirmation", handle_confirmation)

    # --- Route targets — every node can go to every other node -----------------
    _route_targets: dict[str, str] = {
        "gather_source": "gather_source",
        "gather_destinations": "gather_destinations",
        "handle_clarification": "handle_clarification",
        "handle_confirmation": "handle_confirmation",
        "confirm_intent": "confirm_intent",
        END: END,
    }

    _all_nodes = [
        "parse_initial_intent",
        "gather_source",
        "gather_destinations",
        "handle_clarification",
        "confirm_intent",
        "handle_confirmation",
    ]

    route_map = cast(dict[Hashable, str], _route_targets)
    for node in _all_nodes:
        builder.add_conditional_edges(node, _route_next, route_map)

    return "parse_initial_intent"


def build() -> CompiledStateGraph:
    """Compile the intent_worker sub-graph (for isolated testing)."""
    builder = StateGraph(GlobalAgentState)
    builder.set_entry_point(wire_intent_phase(builder))
    return builder.compile(name="intent_worker")
