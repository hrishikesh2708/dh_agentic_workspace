"""OAuth utilities — mock token detection and generic URL builder.

Mock tokens (starting with 'mock_') are valid in non-production environments.
They allow end-to-end flow testing without real ad platform credentials.

Generic OAuth: builds authorization URLs from a catalog config dict so new
destinations don't require custom endpoint code.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

from app.config import settings


# ---------------------------------------------------------------------------
# Mock token support
# ---------------------------------------------------------------------------

MOCK_TOKEN_PREFIX = "mock_"


def is_mock_token(token: str | None) -> bool:
    """True if this is a dev/test mock token that should bypass real API calls."""
    if not token:
        return False
    env = getattr(settings, "ENVIRONMENT", "production").lower()
    if env == "production":
        return False  # Never allow mock tokens in prod
    return str(token).startswith(MOCK_TOKEN_PREFIX)


def make_mock_token(destination_type: str, project_id: str) -> str:
    """Generate a deterministic mock token for dev use."""
    raw = f"mock_{destination_type}_{project_id}"
    return MOCK_TOKEN_PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_state_token() -> str:
    """Cryptographically random CSRF state token for OAuth flows."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Generic OAuth URL builder catalog
# ---------------------------------------------------------------------------

_OAUTH_CATALOG: dict[str, dict[str, Any]] = {
    "meta_capi": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "scope": "ads_read,ads_management,business_management",
        "client_id_setting": "META_APP_ID",
        "response_type": "code",
        "extra_params": {"auth_type": "rerequest"},
    },
    "google_offline": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scope": ("https://www.googleapis.com/auth/adwords https://www.googleapis.com/auth/userinfo.email"),
        "client_id_setting": "GOOGLE_CLIENT_ID",
        "response_type": "code",
        "extra_params": {
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        },
    },
    "google_dm": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scope": ("https://www.googleapis.com/auth/adwords https://www.googleapis.com/auth/userinfo.email"),
        "client_id_setting": "GOOGLE_CLIENT_ID",
        "response_type": "code",
        "extra_params": {
            "access_type": "offline",
            "prompt": "consent",
        },
    },
    "tiktok": {
        "auth_url": "https://business-api.tiktok.com/open_api/v1.3/oauth2/authorize/",
        "scope": "ad_account:read,campaign:read",
        "client_id_setting": "TIKTOK_APP_ID",
        "response_type": "code",
        "extra_params": {},
    },
    "snapchat": {
        "auth_url": "https://accounts.snapchat.com/login/oauth2/authorize",
        "scope": "snapchat-marketing-api",
        "client_id_setting": "SNAPCHAT_CLIENT_ID",
        "response_type": "code",
        "extra_params": {},
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "scope": "r_ads,rw_ads",
        "client_id_setting": "LINKEDIN_CLIENT_ID",
        "response_type": "code",
        "extra_params": {},
    },
}


def build_oauth_url(
    destination_type: str,
    redirect_uri: str,
    state_token: str,
    extra_params: dict[str, str] | None = None,
) -> str | None:
    """Build an OAuth authorization URL for a destination from the catalog.

    Returns None if the destination is not in the catalog or is misconfigured.
    """
    config = _OAUTH_CATALOG.get(destination_type)
    if not config:
        return None

    client_id_key = config.get("client_id_setting", "")
    client_id = getattr(settings, client_id_key, "") if client_id_key else ""
    if not client_id:
        return None  # Not configured

    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": config.get("response_type", "code"),
        "scope": config.get("scope", ""),
        "state": state_token,
        **(config.get("extra_params") or {}),
        **(extra_params or {}),
    }

    return config["auth_url"] + "?" + urlencode(params)


def get_supported_oauth_destinations() -> list[str]:
    """Return destination types that have catalog OAuth entries."""
    return list(_OAUTH_CATALOG.keys())
