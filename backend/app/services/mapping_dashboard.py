"""Service layer for the dashboard REST endpoints.

Encapsulates async DB access for mapping sessions, field mappings, and
golden rules. Reuses the shared ``session_maker`` from
``app.agents.core.deps`` so we don't spin up a second async engine.
"""

from typing import (
    List,
    Optional,
    Tuple,
)

from sqlalchemy import (
    delete,
    func,
)
from sqlmodel import (
    col,
    select,
)

from app.agents.core.deps import session_maker
from app.core.logging import logger
from app.models.mapping.field_mapping import FieldMapping
from app.models.mapping.golden_rule import GoldenRule
from app.models.mapping.mapping_session import MappingSession


async def list_user_mappings(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    kind: Optional[str] = None,
) -> Tuple[List[MappingSession], int]:
    """List mapping sessions owned by ``user_id``.

    Args:
        user_id: The current user's id (matched against ``customer_id``).
        limit: Page size.
        offset: Page offset.
        kind: Optional ``mapping_kind`` filter (``canonical``/``projection``).

    Returns:
        Tuple of (page of MappingSession rows, total count).
    """
    async with session_maker() as db:
        base_where = col(MappingSession.customer_id) == user_id

        list_stmt = (
            select(MappingSession)
            .where(base_where)
            .order_by(col(MappingSession.created_at).desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(MappingSession).where(base_where)

        if kind is not None:
            list_stmt = list_stmt.where(col(MappingSession.mapping_kind) == kind)
            count_stmt = count_stmt.where(col(MappingSession.mapping_kind) == kind)

        rows_result = await db.execute(list_stmt)
        rows = list(rows_result.scalars().all())

        count_result = await db.execute(count_stmt)
        total = int(count_result.scalar_one() or 0)

        return rows, total


async def get_user_mapping_detail(
    user_id: int,
    session_id: int,
) -> Optional[Tuple[MappingSession, List[FieldMapping]]]:
    """Return a single mapping session + its field mappings.

    Args:
        user_id: The current user's id; the session is only returned if owned.
        session_id: The mapping-session primary key.

    Returns:
        Tuple of (MappingSession, list of FieldMapping) or ``None`` if the
        session does not exist or is not owned by ``user_id``.
    """
    async with session_maker() as db:
        session_stmt = select(MappingSession).where(
            col(MappingSession.id) == session_id,
            col(MappingSession.customer_id) == user_id,
        )
        result = await db.execute(session_stmt)
        mapping_session = result.scalar_one_or_none()
        if mapping_session is None:
            return None

        fm_stmt = (
            select(FieldMapping).where(col(FieldMapping.session_id) == session_id).order_by(col(FieldMapping.id).asc())
        )
        fm_result = await db.execute(fm_stmt)
        field_mappings = list(fm_result.scalars().all())

        return mapping_session, field_mappings


async def delete_user_mapping(user_id: int, session_id: int) -> bool:
    """Delete a mapping session (and its field_mappings) owned by ``user_id``.

    The Stage 2 migration does not declare an ON DELETE CASCADE on
    ``field_mapping.session_id`` so we explicitly delete child rows first.

    Args:
        user_id: The current user's id.
        session_id: The mapping-session primary key.

    Returns:
        True if the session was deleted, False if it did not exist or was
        not owned by ``user_id``.
    """
    async with session_maker() as db:
        session_stmt = select(MappingSession).where(
            col(MappingSession.id) == session_id,
            col(MappingSession.customer_id) == user_id,
        )
        result = await db.execute(session_stmt)
        mapping_session = result.scalar_one_or_none()
        if mapping_session is None:
            return False

        # Delete child rows first (no cascade in the migration).
        await db.execute(delete(FieldMapping).where(col(FieldMapping.session_id) == session_id))
        await db.delete(mapping_session)
        await db.commit()

        logger.info(
            "mapping_session_deleted",
            session_id=session_id,
            user_id=user_id,
        )
        return True


async def list_golden_rules(
    limit: int = 20,
    offset: int = 0,
    destination_type: Optional[str] = None,
) -> Tuple[List[GoldenRule], int]:
    """List golden rules sorted by ``occurrence_count`` desc.

    Golden rules are global (no per-user scoping in the schema).

    Args:
        limit: Page size.
        offset: Page offset.
        destination_type: Optional filter by destination schema id.

    Returns:
        Tuple of (page of GoldenRule rows, total count).
    """
    async with session_maker() as db:
        list_stmt = (
            select(GoldenRule)
            .order_by(col(GoldenRule.occurrence_count).desc(), col(GoldenRule.id).asc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(GoldenRule)

        if destination_type is not None:
            list_stmt = list_stmt.where(col(GoldenRule.destination_type) == destination_type)
            count_stmt = count_stmt.where(col(GoldenRule.destination_type) == destination_type)

        rows_result = await db.execute(list_stmt)
        rows = list(rows_result.scalars().all())

        count_result = await db.execute(count_stmt)
        total = int(count_result.scalar_one() or 0)

        return rows, total


async def create_golden_rule(
    source_pattern: str,
    destination_field: str,
    destination_type: str,
    occurrence_count: int = 1,
) -> GoldenRule:
    """Create a new golden rule.

    Args:
        source_pattern: Lowercased source field pattern.
        destination_field: Destination field this pattern maps to.
        destination_type: Destination schema id.
        occurrence_count: Initial occurrence count (default 1).

    Returns:
        The created GoldenRule with primary key populated.
    """
    async with session_maker() as db:
        rule = GoldenRule(
            source_pattern=source_pattern,
            destination_field=destination_field,
            destination_type=destination_type,
            occurrence_count=occurrence_count,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)

        logger.info(
            "golden_rule_created",
            rule_id=rule.id,
            source_pattern=source_pattern,
            destination_field=destination_field,
            destination_type=destination_type,
        )
        return rule


async def delete_golden_rule(rule_id: int) -> bool:
    """Delete a golden rule by id.

    Args:
        rule_id: The golden-rule primary key.

    Returns:
        True if the rule was deleted, False if it did not exist.
    """
    async with session_maker() as db:
        stmt = select(GoldenRule).where(col(GoldenRule.id) == rule_id)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule is None:
            return False

        await db.delete(rule)
        await db.commit()

        logger.info("golden_rule_deleted", rule_id=rule_id)
        return True
