"""intent_worker — parse the user's mapping intent + HITL-gather missing slots.

Runs first in the supervisor pipeline. Extracts ``source`` / ``source_object``
/ ``destination_type`` from the user message via an LLM, then loops through
HITL pickers until all three slots are valid.

Import ``build`` from :mod:`app.agents.workers.intent_worker.graph` directly.
This package's ``__init__`` is deliberately empty: importing ``build`` here
would trigger ``graph.py`` → ``core.messages`` → ``core.deps`` → worker
``tools`` modules, which then re-trigger this ``__init__`` while it's mid-load
(circular import).
"""
