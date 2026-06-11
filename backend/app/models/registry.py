"""Register all SQLModel tables before any ORM queries run.

Import this module once at app startup (e.g. from ``database.py``) so
SQLAlchemy can resolve every ``Relationship()`` target. Mirrors
``alembic/env.py`` model imports.
"""

from app.models.canonical_field import CanonicalField  # noqa: F401
from app.models.connector import Connector  # noqa: F401
from app.models.destination_field_mapping import DestinationFieldMapping  # noqa: F401
from app.models.field_mapping import FieldMapping  # noqa: F401
from app.models.golden_rule import GoldenRule  # noqa: F401
from app.models.mapping_embedding import MappingEmbedding  # noqa: F401
from app.models.mapping_session import MappingSession  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.project_connection import ProjectConnection  # noqa: F401
from app.models.project_connection_secret import ProjectConnectionSecret  # noqa: F401
from app.models.project_field_mapping import ProjectFieldMapping  # noqa: F401
from app.models.project_integration import ProjectIntegration  # noqa: F401
from app.models.project_source_module import ProjectSourceModule  # noqa: F401
from app.models.session import Session  # noqa: F401
from app.models.thread import Thread  # noqa: F401
from app.models.user import User  # noqa: F401
