"""This file contains the session model for the application."""

from typing import (
    TYPE_CHECKING,
    Optional,
)
from uuid import UUID

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Session(BaseModel, table=True):
    """Session model for storing chat sessions.

    Attributes:
        id: The primary key
        user_id: Foreign key to the user
        project_id: Project workspace this session is scoped to.
                    Set by the frontend when opening the Copilot from a project
                    context; used to scope all connection/mapping DB queries.
        name: Name of the session (defaults to empty string)
        username: Display name copied from the user at session creation
        created_at: When the session was created
        messages: Relationship to session messages
        user: Relationship to the session owner
    """

    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    project_id: Optional[UUID] = Field(default=None, foreign_key="project.id", index=True)
    name: str = Field(default="")
    username: Optional[str] = Field(default=None)
    user: "User" = Relationship(back_populates="sessions")
