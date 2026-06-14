"""Pydantic schemas for project workspace endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Payload for creating a new project workspace."""

    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    """Response schema for a single project workspace."""

    id: UUID
    user_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated list of project workspaces."""

    items: list[ProjectRead]
    total: int
