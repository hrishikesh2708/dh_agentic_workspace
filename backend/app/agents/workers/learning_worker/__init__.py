"""learning_worker — persist mapping sessions + learn from human feedback.

Runs after the reviewer_worker. ``persist`` writes the session + field
mappings; ``learn`` upserts pgvector embeddings + golden rules for any
human-approved or human-corrected mappings.

Import ``build`` from :mod:`app.agents.workers.learning_worker.graph` directly.
This package's ``__init__`` is deliberately empty to avoid a circular import
via ``deps`` at package-load time.
"""
