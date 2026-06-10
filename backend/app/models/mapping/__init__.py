"""SQLModel ORM models for the mapping agent.

These are the framework-blessed home for the tables that crawler_agent
previously had in ``persistence/models.py``. Each table:

- ``mapping_session`` — one row per agent run (canonical or projection).
- ``field_mapping``   — one source→destination proposal, scoped to a session.
- ``mapping_embedding`` — pgvector embedding for an approved field_mapping.
- ``golden_rule``     — learned (source_pattern, destination_field) with count.

The ``customer_id`` column on ``mapping_session`` foreign-keys to the
framework's ``user.id``. The field name is kept (vs renaming to
``user_id``) to minimise churn against the ported pipeline code that
already references it.

The ``Customer`` table is intentionally **not** ported — under our
personal/single-user tenancy model the framework's ``User`` is the customer.
"""

from app.models.mapping.field_mapping import FieldMapping
from app.models.mapping.golden_rule import GoldenRule
from app.models.mapping.mapping_embedding import MappingEmbedding
from app.models.mapping.mapping_session import MappingSession

__all__ = [
    "FieldMapping",
    "GoldenRule",
    "MappingEmbedding",
    "MappingSession",
]
