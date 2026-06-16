"""Application configuration management.

This module handles environment-specific configuration loading, parsing, and management
for the application. It includes environment detection, .env file loading, and
configuration value parsing.
"""

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


# Define environment types
class Environment(str, Enum):
    """Application environment types.

    Defines the possible environments the application can run in:
    development, staging, production, and test.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


# Determine environment
def get_environment() -> Environment:
    """Get the current environment.

    Returns:
        Environment: The current environment (development, staging, production, or test)
    """
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


# Load appropriate .env file based on environment
def load_env_file():
    """Load environment-specific .env file."""
    env = get_environment()
    print(f"Loading environment: {env}")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Define env files in priority order
    env_files = [
        os.path.join(base_dir, f".env.{env.value}.local"),
        os.path.join(base_dir, f".env.{env.value}"),
        os.path.join(base_dir, ".env.local"),
        os.path.join(base_dir, ".env"),
    ]

    # Load the first env file that exists
    for env_file in env_files:
        if os.path.isfile(env_file):
            load_dotenv(dotenv_path=env_file)
            print(f"Loaded environment from {env_file}")
            return env_file

    # Fall back to default if no env file found
    return None


ENV_FILE = load_env_file()


# Parse list values from environment variables
def parse_list_from_env(env_key, default=None):
    """Parse a comma-separated list from an environment variable."""
    value = os.getenv(env_key)
    if not value:
        return default or []

    # Remove quotes if they exist
    value = value.strip("\"'")
    # Handle single value case
    if "," not in value:
        return [value]
    # Split comma-separated values
    return [item.strip() for item in value.split(",") if item.strip()]


# Parse dict of lists from environment variables with prefix
def parse_dict_of_lists_from_env(prefix, default_dict=None):
    """Parse dictionary of lists from environment variables with a common prefix."""
    result = default_dict or {}

    # Look for all env vars with the given prefix
    for key, value in os.environ.items():
        if key.startswith(prefix):
            endpoint = key[len(prefix) :].lower()  # Extract endpoint name
            # Parse the values for this endpoint
            if value:
                value = value.strip("\"'")
                if "," in value:
                    result[endpoint] = [item.strip() for item in value.split(",") if item.strip()]
                else:
                    result[endpoint] = [value]

    return result


class Settings:
    """Application settings without using pydantic."""

    def __init__(self):
        """Initialize application settings from environment variables.

        Loads and sets all configuration values from environment variables,
        with appropriate defaults for each setting. Also applies
        environment-specific overrides based on the current environment.
        """
        # Set the environment
        self.ENVIRONMENT = get_environment()

        # Application Settings
        self.PROJECT_NAME = os.getenv("PROJECT_NAME", "FastAPI LangGraph Template")
        self.VERSION = os.getenv("VERSION", "1.0.0")
        self.DESCRIPTION = os.getenv(
            "DESCRIPTION", "A production-ready FastAPI template with LangGraph and LangSmith integration"
        )
        self.API_V1_STR = os.getenv("API_V1_STR", "/api/v1")
        self.DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t", "yes")

        # CORS Settings
        self.ALLOWED_ORIGINS = parse_list_from_env("ALLOWED_ORIGINS", ["*"])

        # LangSmith Configuration
        self.LANGSMITH_TRACING_ENABLED = os.getenv("LANGSMITH_TRACING_ENABLED", "true").lower() in (
            "true",
            "1",
            "t",
            "yes",
        )
        self.LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
        self.LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "default")
        self.LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

        # LangGraph Configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gpt-5-mini")
        self.SESSION_NAMING_ENABLED = os.getenv("SESSION_NAMING_ENABLED", "true").lower() == "true"
        self.DEFAULT_LLM_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))
        self.MAX_LLM_CALL_RETRIES = int(os.getenv("MAX_LLM_CALL_RETRIES", "3"))
        self.LLM_TOTAL_TIMEOUT = int(os.getenv("LLM_TOTAL_TIMEOUT", "60"))

        # Long term memory Configuration
        self.LONG_TERM_MEMORY_MODEL = os.getenv("LONG_TERM_MEMORY_MODEL", "gpt-5-nano")
        self.LONG_TERM_MEMORY_EMBEDDER_MODEL = os.getenv("LONG_TERM_MEMORY_EMBEDDER_MODEL", "text-embedding-3-small")
        self.LONG_TERM_MEMORY_COLLECTION_NAME = os.getenv("LONG_TERM_MEMORY_COLLECTION_NAME", "longterm_memory")
        # JWT Configuration
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_DAYS", "30"))

        # Logging Configuration
        self.LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "console"

        # Profiling Configuration (DEBUG only)
        self.PROFILING_DIR = Path(os.getenv("PROFILING_DIR", "/tmp/fastapi_profiles"))
        self.PROFILING_THRESHOLD_SECONDS = float(os.getenv("PROFILING_THRESHOLD_SECONDS", "2.0"))

        # Postgres Configuration
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", "food_order_db")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
        self.POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
        self.POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))
        self.CHECKPOINT_TABLES = ["checkpoint_blobs", "checkpoint_writes", "checkpoints"]

        # Valkey/Redis Cache Configuration (optional — if host is set, caching is enabled)
        self.VALKEY_HOST = os.getenv("VALKEY_HOST", "")
        self.VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
        self.VALKEY_DB = int(os.getenv("VALKEY_DB", "0"))
        self.VALKEY_PASSWORD = os.getenv("VALKEY_PASSWORD", "")
        self.VALKEY_MAX_CONNECTIONS = int(os.getenv("VALKEY_MAX_CONNECTIONS", "20"))
        self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))

        # Rate Limiting Configuration
        self.RATE_LIMIT_DEFAULT = parse_list_from_env("RATE_LIMIT_DEFAULT", ["200 per day", "50 per hour"])

        # Rate limit endpoints defaults
        default_endpoints = {
            "chat": ["30 per minute"],
            "chat_stream": ["20 per minute"],
            "messages": ["50 per minute"],
            "register": ["10 per hour"],
            "login": ["20 per minute"],
            "root": ["10 per minute"],
            "health": ["20 per minute"],
            "mappings_list": ["120 per minute"],
            "mappings_detail": ["60 per minute"],
            "golden_rules": ["60 per minute"],
            "integrations": ["30 per minute"],
            "projects": ["60 per minute"],
        }

        # Update rate limit endpoints from environment variables
        self.RATE_LIMIT_ENDPOINTS = default_endpoints.copy()
        for endpoint in default_endpoints:
            env_key = f"RATE_LIMIT_{endpoint.upper()}"
            value = parse_list_from_env(env_key)
            if value:
                self.RATE_LIMIT_ENDPOINTS[endpoint] = value

        # ---------------------------------------------------------------
        # Mapping Agent Configuration (Stage 1)
        # ---------------------------------------------------------------
        # LLM + embedding models the mapper uses (separate from chat LLMs)
        self.MAPPING_LLM_MODEL = os.getenv("MAPPING_LLM_MODEL", "gpt-4o")
        self.MAPPING_EMBEDDER_MODEL = os.getenv("MAPPING_EMBEDDER_MODEL", "text-embedding-3-small")

        # Confidence-gating thresholds (auto-approve / review / unmatched)
        self.AUTO_APPROVE_THRESHOLD = float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.90"))
        self.REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.50"))

        # Feedback learning
        self.GOLDEN_RULE_MIN_OCCURRENCES = int(os.getenv("GOLDEN_RULE_MIN_OCCURRENCES", "3"))
        self.MAPPER_TOP_K_EXAMPLES = int(os.getenv("MAPPER_TOP_K_EXAMPLES", "5"))

        # Schema registry paths (relative to backend/app/services/)
        self.DESTINATION_SCHEMA_DIR = os.getenv("DESTINATION_SCHEMA_DIR", "schemas/destinations")
        self.INTERNAL_SCHEMA_DIR = os.getenv("INTERNAL_SCHEMA_DIR", "schemas/internal")
        self.INTERNAL_SCHEMA_NAME = os.getenv("INTERNAL_SCHEMA_NAME", "canonical")

        # Salesforce integration (OAuth2 Authorization Code + PKCE)
        self.SALESFORCE_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID", "")
        self.SALESFORCE_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET", "")
        self.SALESFORCE_AUTH_URL = os.getenv("SALESFORCE_AUTH_URL", "https://login.salesforce.com")

        # Meta (Facebook) integration
        self.META_APP_ID = os.getenv("META_APP_ID", "")
        self.META_APP_SECRET = os.getenv("META_APP_SECRET", "")

        # Google integration
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

        # TikTok integration
        self.TIKTOK_APP_ID = os.getenv("TIKTOK_APP_ID", "")
        self.TIKTOK_APP_SECRET = os.getenv("TIKTOK_APP_SECRET", "")

        # Snapchat integration
        self.SNAPCHAT_CLIENT_ID = os.getenv("SNAPCHAT_CLIENT_ID", "")
        self.SNAPCHAT_CLIENT_SECRET = os.getenv("SNAPCHAT_CLIENT_SECRET", "")

        # Base URL used to build OAuth callback URIs.
        # Must exactly match what is registered in each provider's app settings.
        # Defaults to http://localhost:8000 for local dev.
        self.OAUTH_CALLBACK_BASE_URL = os.getenv("OAUTH_CALLBACK_BASE_URL", "http://localhost:8000")
        self.SALESFORCE_STANDARD_OBJECTS = os.getenv(
            "SALESFORCE_STANDARD_OBJECTS",
            "Lead,Contact,Account,Opportunity,Case,Campaign,Task,Event,CampaignMember,Order,Product2,Quote",
        )

        # Evaluation Configuration
        self.EVALUATION_LLM = os.getenv("EVALUATION_LLM", "gpt-5")
        self.EVALUATION_BASE_URL = os.getenv("EVALUATION_BASE_URL", "https://api.openai.com/v1")
        self.EVALUATION_API_KEY = os.getenv("EVALUATION_API_KEY", self.OPENAI_API_KEY)
        self.EVALUATION_SLEEP_TIME = int(os.getenv("EVALUATION_SLEEP_TIME", "10"))

        # Apply environment-specific settings
        self.apply_environment_settings()

    def apply_environment_settings(self):
        """Apply environment-specific settings based on the current environment."""
        env_settings = {
            Environment.DEVELOPMENT: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "200 per hour"],
            },
            Environment.STAGING: {
                "DEBUG": False,
                "LOG_LEVEL": "INFO",
                "RATE_LIMIT_DEFAULT": ["500 per day", "100 per hour"],
            },
            Environment.PRODUCTION: {
                "DEBUG": False,
                "LOG_LEVEL": "WARNING",
                "RATE_LIMIT_DEFAULT": ["200 per day", "50 per hour"],
            },
            Environment.TEST: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "1000 per hour"],  # Relaxed for testing
            },
        }

        # Get settings for current environment
        current_env_settings = env_settings.get(self.ENVIRONMENT, {})

        # Apply settings if not explicitly set in environment variables
        for key, value in current_env_settings.items():
            env_var_name = key.upper()
            # Only override if environment variable wasn't explicitly set
            if env_var_name not in os.environ:
                setattr(self, key, value)


# Create settings instance
settings = Settings()
