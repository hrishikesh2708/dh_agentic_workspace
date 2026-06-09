"""reviewer_worker — validate, score, and HITL-review proposed mappings.

Runs in both canonical and projection stages. Emits a ``mapping_review``
interrupt when any mapping needs human input; otherwise persists the
auto-approved mappings immediately (canonical only) and falls through.

Import ``build`` from :mod:`app.agents.workers.reviewer_worker.graph` directly.
This package's ``__init__`` is deliberately empty to avoid a circular import
via ``deps`` at package-load time.
"""
