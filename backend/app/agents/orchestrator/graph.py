"""Supervisor graph — sequences all 8 worker sub-graphs.

Phase flow (each phase wired with next_phase_entry for same-turn chaining)::

    welcome
       │
    [intent phase]      parse_initial_intent → gather_source/dests → confirm_intent
       │
    [connection phase]  check_source_connection → gather_object → check_channel_connections
       │
    [funnel phase]      check_funnel_needed → gather_funnel_stages
       │
    [mapping phase]     fetch_schemas → run_mapping → canonical_mapping → resolve_fields → mapping_complete
       │
    [validation phase]  validate_mappings → show_validation_errors (loop if errors)
       │
    [confirm phase]     show_confirmation → verify_confirmation (loop until token match)
       │
    [activation phase]  run_activation
       │
      END

All workers are flattened into the supervisor graph (not nested subgraphs).
This keeps HITL interrupts and AIMessages on the supervisor thread so
CopilotKit/AG-UI can stream them to the UI correctly.

Each wire_*_phase(g, next_phase_entry=...) function receives the entry node
of the following phase, enabling same-turn chaining without duplicate edges.

Cross-turn re-entry via route_after_welcome — on each new user message,
the supervisor inspects phase_complete booleans and routes to the correct
phase entry point.
"""

from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.orchestrator.state import GlobalAgentState
from app.agents.workers.activation_worker.graph import wire_activation_phase
from app.agents.workers.confirm_worker.graph import wire_confirm_phase
from app.agents.workers.connection_worker.graph import wire_connection_phase
from app.agents.workers.funnel_worker.graph import wire_funnel_phase
from app.agents.workers.intent_worker.graph import route_after_intent, wire_intent_phase
from app.agents.workers.mapping_worker.graph import wire_mapping_phase
from app.agents.workers.validation_worker.graph import wire_validation_phase
from app.agents.workers.welcome_worker.tools import route_after_welcome, welcome_user


def _build_supervisor() -> StateGraph:
    g = StateGraph(GlobalAgentState)

    # -------------------------------------------------------------------------
    # Phase 0: Welcome
    # -------------------------------------------------------------------------
    g.add_node("welcome", welcome_user)

    # -------------------------------------------------------------------------
    # Register phases in reverse so each wire call knows the next entry node.
    # -------------------------------------------------------------------------

    # Phase 7: Activation → END
    activation_entry = wire_activation_phase(g)

    # Phase 6: Confirmation → activation
    confirm_entry = wire_confirm_phase(g, next_phase_entry=activation_entry)

    # Phase 5: Validation → confirmation; back-edge to mapping on edit_mapping
    # mapping_entry not yet defined — we pass a sentinel and patch below.
    # Instead, use the pattern: validation exits to END, supervisor re-routes.
    # The mapping back-edge is handled by route_after_welcome (pending_action).
    validation_entry = wire_validation_phase(
        g,
        next_phase_entry=confirm_entry,
        mapping_re_entry=END,  # patched after mapping_entry is known below
    )

    # Phase 4: Mapping → validation
    mapping_entry = wire_mapping_phase(g, next_phase_entry=validation_entry)

    # Phase 3: Funnel → mapping
    funnel_entry = wire_funnel_phase(g, next_phase_entry=mapping_entry)

    # Phase 2: Connection → funnel
    connection_entry = wire_connection_phase(g, next_phase_entry=funnel_entry)

    # Phase 1: Intent (flattened nodes)
    intent_entry = wire_intent_phase(g)

    # -------------------------------------------------------------------------
    # Supervisor edges
    # -------------------------------------------------------------------------

    # START → welcome
    g.add_edge(START, "welcome")

    # welcome → current phase (or END to wait for next user turn)
    g.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            # Intent phase
            "intent": intent_entry,
            "handle_clarification": "handle_clarification",
            "handle_confirmation": "handle_confirmation",
            # Later phases — re-entry after a new user message
            "funnel_phase": funnel_entry,
            "mapping_phase": mapping_entry,
            "validation_phase": validation_entry,
            "confirm_phase": confirm_entry,
            "activation_phase": activation_entry,
            END: END,
        },
    )

    # Intent complete → connection phase
    g.add_conditional_edges(
        "handle_confirmation",
        route_after_intent,
        {"connection_phase": connection_entry, END: END},
    )

    # Connection → funnel is wired internally via wire_connection_phase(next_phase_entry=funnel_entry).
    # Funnel → mapping is wired internally via wire_funnel_phase(next_phase_entry=mapping_entry).
    # Mapping → validation is wired internally via wire_mapping_phase(next_phase_entry=validation_entry).
    # Validation → confirm is wired internally via wire_validation_phase(next_phase_entry=confirm_entry).
    # Confirm → activation is wired internally via wire_confirm_phase(next_phase_entry=activation_entry).

    return g


def build_studio_graph() -> CompiledStateGraph:
    """Compile the supervisor graph without a checkpointer (``langgraph dev``)."""
    return _build_supervisor().compile(name="datahash_agent")


def build_app_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Compile the supervisor graph with an optional Postgres checkpointer."""
    return _build_supervisor().compile(
        checkpointer=checkpointer,
        name="datahash_agent",
    )
