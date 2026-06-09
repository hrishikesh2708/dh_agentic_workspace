r"""intent_worker sub-graph.

Layout (mirrors the routing crawler_agent did inside its supervisor)::

    parse_initial_intent
            │
            ▼
        [router]
       /   |   \
      ▼    ▼    ▼
   gather_  gather_  gather_
   source   object   destination
      │       │        │
      ▼       ▼        ▼
        [router] ──► END

After every gather node we re-enter the router so missing slots are
filled in order. When all three slots (source / source_object /
destination_type) are present, the router routes to ``END``.
"""

from __future__ import annotations

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph

from app.agents.core import deps
from app.agents.core.intent_validation import (
    is_valid_destination,
    is_valid_source,
    normalize_optional_str,
)
from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.intent_worker.tools import (
    gather_destination,
    gather_object,
    gather_source,
    parse_initial_intent,
)


async def _route_next(state: GlobalAgentState) -> str:
    """Pick the next gather node based on which slot is still empty."""
    source = state.source.value if state.source else ""
    if not is_valid_source(source):
        return "gather_source"
    if not normalize_optional_str(state.source_object):
        return "gather_object"

    valid_dest_ids = await deps.catalog.enabled_destination_ids()
    if not is_valid_destination(state.destination_type, valid_dest_ids):
        return "gather_destination"
    return END


def build() -> CompiledStateGraph:
    """Compile the intent_worker sub-graph."""
    builder = StateGraph(GlobalAgentState)
    builder.add_node("parse_initial_intent", parse_initial_intent)
    builder.add_node("gather_source", gather_source)
    builder.add_node("gather_object", gather_object)
    builder.add_node("gather_destination", gather_destination)

    builder.set_entry_point("parse_initial_intent")

    # After parse, route to the first missing slot (or END).
    builder.add_conditional_edges(
        "parse_initial_intent",
        _route_next,
        {
            "gather_source": "gather_source",
            "gather_object": "gather_object",
            "gather_destination": "gather_destination",
            END: END,
        },
    )
    # After each gather, re-enter the router so the next missing slot is filled.
    for node in ("gather_source", "gather_object", "gather_destination"):
        builder.add_conditional_edges(
            node,
            _route_next,
            {
                "gather_source": "gather_source",
                "gather_object": "gather_object",
                "gather_destination": "gather_destination",
                END: END,
            },
        )

    return builder.compile(name="intent_worker")
