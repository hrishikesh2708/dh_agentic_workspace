"""Pydantic schemas for project workspace endpoints."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.base import BaseResponse


class ProjectRead(BaseModel):
    """A user-owned project workspace.

    Attributes:
        id: Project UUID.
        name: Human-readable project name.
        description: Optional longer description.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Project UUID")
    name: str = Field(..., description="Human-readable project name")
    description: Optional[str] = Field(default=None, description="Optional project description")
    created_at: datetime = Field(..., description="Row creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")


class ProjectCreate(BaseModel):
    """Request body for creating a project workspace.

    Attributes:
        name: Human-readable project name (unique per user).
        description: Optional longer description.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(default=None, max_length=2000, description="Optional description")

    @field_validator("name", "description")
    @classmethod
    def strip_value(cls, v: Optional[str]) -> Optional[str]:
        """Trim leading / trailing whitespace."""
        if v is None:
            return None
        return v.strip()


class ProjectListResponse(BaseResponse):
    """List of projects owned by the current user.

    Attributes:
        items: All projects for the user (typically a small list).
        total: Total number of projects.
    """

    items: List[ProjectRead] = Field(default_factory=list, description="User's projects")
    total: int = Field(..., description="Total number of projects")
