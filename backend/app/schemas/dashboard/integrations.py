"""Pydantic schemas for integration (Salesforce OAuth) dashboard endpoints."""

from typing import Optional

from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.base import BaseResponse


class SalesforceStatus(BaseResponse):
    """Salesforce connection status for the current user.

    Attributes:
        connected: Whether the user has an active Salesforce connection.
        auth_url: OAuth authorise URL the frontend should redirect to.
    """

    connected: bool = Field(..., description="Whether the user has an active Salesforce connection")
    auth_url: str = Field(..., description="Salesforce OAuth authorise URL")


class SalesforceOAuthCallback(BaseModel):
    """Request body for the Salesforce OAuth callback.

    Attributes:
        code: Authorization code returned by Salesforce.
        state: Opaque state token used to mitigate CSRF.
    """

    code: str = Field(..., min_length=1, description="Authorization code from Salesforce")
    state: Optional[str] = Field(default=None, description="Opaque CSRF mitigation token")
