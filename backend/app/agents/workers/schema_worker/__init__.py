"""schema_worker — extracts the source schema and loads the destination schema.

Canonical mode: fan-out (extract_source ∥ load_internal_canonical).
Projection mode: load destination from the destination registry.

Import ``build`` from :mod:`app.agents.workers.schema_worker.graph` directly.
Kept empty here to avoid a circular import via ``deps`` at package-load time.
"""
