"""``oauth_pending`` table — transient PKCE state during OAuth flows.

One row per in-flight OAuth handshake (source or destination).
Deleted immediately after the callback completes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel


class OAuthPending(SQLModel, table=True):
    """Transient PKCE verifier for an in-flight OAuth handshake.

    Keyed by ``state`` — the opaque nonce passed to the OAuth provider and
    echoed back in the callback URL. One row covers both source (Salesforce)
    and destination (Meta, Google, TikTok, …) connectors; ``connector_slug``
    tells the callback which platform's token exchange to call.

    Attributes:
        state: Random nonce, primary key, sent as OAuth ``state`` param.
        connector_slug: Connector being authorised (e.g. ``salesforce``).
        project_id: Project this connection will belong to.
        session_id: Browser session that initiated the flow (tab-scoped).
        pkce_verifier: PKCE code_verifier (None for connectors without PKCE).
        created_at: Row creation timestamp; used for TTL-based cleanup.
    """

    __tablename__ = "oauth_pending"  # type: ignore[assignment]

    state: str = Field(primary_key=True)
    connector_slug: str = Field(index=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    session_id: str
    pkce_verifier: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
