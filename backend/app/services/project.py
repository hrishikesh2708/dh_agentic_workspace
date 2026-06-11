"""Database operations for user-owned project workspaces."""

from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)
from sqlmodel import (
    Session,
    col,
    select,
)

from app.core.logging import logger
from app.models.project import Project
from app.services.database import DatabaseService

_db = DatabaseService()


def list_user_projects(user_id: int) -> List[Project]:
    """Return all projects owned by a user, newest first."""
    with Session(_db.engine) as session:
        stmt = select(Project).where(col(Project.user_id) == user_id).order_by(col(Project.created_at).desc())
        return list(session.exec(stmt).all())


def get_user_project(user_id: int, project_id: UUID) -> Optional[Project]:
    """Return a project if it belongs to the given user."""
    with Session(_db.engine) as session:
        project = session.get(Project, project_id)
        if project is None or project.user_id != user_id:
            return None
        return project


def create_user_project(
    user_id: int,
    *,
    name: str,
    description: Optional[str] = None,
) -> Project:
    """Create a project workspace for the user."""
    project = Project(user_id=user_id, name=name, description=description)
    with Session(_db.engine) as session:
        try:
            session.add(project)
            session.commit()
            session.refresh(project)
            logger.info("project_created", user_id=user_id, project_id=str(project.id), name=name)
            return project
        except IntegrityError as exc:
            session.rollback()
            logger.warning(
                "project_create_conflict",
                user_id=user_id,
                name=name,
                error=str(exc.orig) if exc.orig else str(exc),
            )
            raise HTTPException(
                status_code=409,
                detail="A project with this name already exists",
            ) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            logger.exception(
                "project_create_failed",
                user_id=user_id,
                name=name,
                error=str(exc),
            )
            raise HTTPException(
                status_code=500,
                detail="Could not create project",
            ) from exc
