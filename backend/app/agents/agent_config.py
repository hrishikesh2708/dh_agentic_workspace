"""Agent config adapter.

The ported mapping-agent code uses lowercase ``settings.<attr>`` (pydantic-
settings convention from crawler_agent), while the datahash framework's
:class:`app.core.config.Settings` uses UPPER_SNAKE_CASE. This module exposes
a single ``agent_settings`` proxy that bridges the two so the ported code
stays untouched.

The adapter is read-only and lazy — values reflect the live state of
``app.config.settings``.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from app.config import settings as _settings

# Anchor for relative schema paths in ``app/services/``
_SHARED_TOOLS_ROOT = Path(__file__).resolve().parent.parent.parent / "services"


def resolve_agent_path(relative: str) -> Path:
    """Resolve a relative path against ``app/services/``.

    Absolute paths are returned unchanged.

    Args:
        relative: Path relative to ``app/services/`` (e.g.
            ``"schemas/destinations"``) or an absolute path.

    Returns:
        Absolute filesystem path.
    """
    path = Path(relative)
    if path.is_absolute():
        return path
    return _SHARED_TOOLS_ROOT / path


class _AgentSettingsProxy:
    """Lowercase-attribute proxy over the global :class:`Settings`."""

    # --- OpenAI ---
    @property
    def openai_api_key(self) -> str:
        return _settings.OPENAI_API_KEY

    @property
    def openai_chat_model(self) -> str:
        return _settings.MAPPING_LLM_MODEL

    @property
    def openai_embedding_model(self) -> str:
        return _settings.MAPPING_EMBEDDER_MODEL

    # --- Salesforce ---
    @property
    def salesforce_client_id(self) -> str:
        return _settings.SALESFORCE_CLIENT_ID

    @property
    def salesforce_client_secret(self) -> str:
        return _settings.SALESFORCE_CLIENT_SECRET

    @property
    def salesforce_auth_url(self) -> str:
        return _settings.SALESFORCE_AUTH_URL

    @property
    def salesforce_standard_objects(self) -> str:
        return _settings.SALESFORCE_STANDARD_OBJECTS

    # --- Schema registry paths ---
    @property
    def destination_schema_dir(self) -> str:
        return _settings.DESTINATION_SCHEMA_DIR

    @property
    def internal_schema_dir(self) -> str:
        return _settings.INTERNAL_SCHEMA_DIR

    @property
    def internal_schema_name(self) -> str:
        return _settings.INTERNAL_SCHEMA_NAME

    # --- Mapper thresholds ---
    @property
    def auto_approve_threshold(self) -> float:
        return _settings.AUTO_APPROVE_THRESHOLD

    @property
    def review_threshold(self) -> float:
        return _settings.REVIEW_THRESHOLD

    @property
    def golden_rule_min_occurrences(self) -> int:
        return _settings.GOLDEN_RULE_MIN_OCCURRENCES

    @property
    def mapper_top_k_examples(self) -> int:
        return _settings.MAPPER_TOP_K_EXAMPLES

    # --- Database (asyncpg URL built from framework's POSTGRES_* settings) ---
    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{quote_plus(_settings.POSTGRES_USER)}:{quote_plus(_settings.POSTGRES_PASSWORD)}"
            f"@{_settings.POSTGRES_HOST}:{_settings.POSTGRES_PORT}/{_settings.POSTGRES_DB}"
        )


agent_settings = _AgentSettingsProxy()
