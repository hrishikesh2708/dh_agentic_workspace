"""Alembic environment configuration.

Loads the database URL from the application's settings so migrations
stay in sync with the running app configuration.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from app.core.config import settings
from app.models.canonical_field import CanonicalField  # noqa: F401
from app.models.connector import Connector  # noqa: F401
from app.models.oauth_pending import OAuthPending  # noqa: F401
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

# Alembic Config object
config = context.config

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Build the database URL from app settings
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Point Alembic at our SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata

# Tables managed by external systems (LangGraph checkpointer, mem0, pgvector)
# that Alembic should never touch.
EXCLUDE_TABLES = {
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
    "checkpoints",
    "longterm_memory",
    "mem0migrations",
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter out tables managed by external systems."""
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout instead of executing against the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an engine and runs migrations against the live database.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
