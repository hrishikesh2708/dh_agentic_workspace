"""learning_worker pipeline agent + session persistence helpers.

Ported from three crawler_agent files:

- ``src/persistence/sessions.py``       → :func:`persist_session`,
   :func:`apply_review_response`
- ``src/persistence/models.py``         → :class:`Customer`,
   :class:`MappingSession`, :class:`FieldMapping`, :class:`MappingEmbedding`,
   :class:`GoldenRule` (inlined here as a TEMPORARY measure; see
   ``TODO(stage-2)`` below)
- ``src/pipeline/feedback_learner.py``  → :class:`FeedbackLearningAgent`

# TODO(stage-2): move ORM models to ``app/models/mapping/`` and wire them
# into the existing :class:`app.models.base.BaseModel` declarative base.
# Inlining them here keeps Stage 1 self-contained — once Stage 2 lands the
# Alembic migrations + the proper model package, delete the model
# definitions in this file and import them from ``app.models.mapping``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)

try:
    from pgvector.sqlalchemy import Vector as _PgVector  # type: ignore[import-not-found]

    _VectorColumnType: Any = _PgVector(1536)
except ImportError:
    # pgvector isn't installed in the backend env yet (Stage 2 will add it).
    # The actual embedding writes go through raw SQL in
    # :mod:`app.agents.shared_tools.vector_store`, so the column type here
    # is unused at runtime. JSON keeps the ORM happy.
    _VectorColumnType = JSON
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from app.agents.core.agent_config import _AgentSettingsProxy
from app.agents.shared_tools.openai_client import OpenAIService
from app.agents.shared_tools.vector_store import VectorStoreService
from app.schemas.agent.types import MappingStatus


# -----------------------------------------------------------------------------
# Inlined ORM models — TODO(stage-2): move to app/models/mapping/
# -----------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Local declarative base for the mapping-agent ORM models.

    Kept separate from :class:`app.models.base.BaseModel` until Stage 2
    consolidates the schemas. The async engine in
    :mod:`app.agents.core.deps` is the one that binds to this metadata.
    """


class Customer(Base):
    """Customer / tenant row (one row per organisation)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    salesforce_org_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list["MappingSession"]] = relationship(back_populates="customer")


class MappingSession(Base):
    """One mapping run (canonical or projection) per row."""

    __tablename__ = "mapping_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending")
    mapping_kind: Mapped[str] = mapped_column(String(32), default="canonical")
    canonical_session_id: Mapped[int | None] = mapped_column(ForeignKey("mapping_sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="sessions")
    mappings: Mapped[list["FieldMapping"]] = relationship(back_populates="session")


class FieldMapping(Base):
    """One source-field → destination-field row, scoped to a mapping session."""

    __tablename__ = "field_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mapping_sessions.id"), nullable=False)
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(64), default="needs_review")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    transformation: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), default="pass")
    validation_notes: Mapped[dict] = mapped_column(JSON, default=list)

    session: Mapped["MappingSession"] = relationship(back_populates="mappings")
    embedding: Mapped["MappingEmbedding"] = relationship(back_populates="field_mapping", uselist=False)


class MappingEmbedding(Base):
    """pgvector embedding for an approved field mapping (used by the mapper retrieval step)."""

    __tablename__ = "mapping_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_mapping_id: Mapped[int] = mapped_column(ForeignKey("field_mappings.id"), nullable=False, unique=True)
    embedding: Mapped[list[float]] = mapped_column(_VectorColumnType)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    field_mapping: Mapped["FieldMapping"] = relationship(back_populates="embedding")


class GoldenRule(Base):
    """High-confidence learned rule: a source pattern that maps to a destination field."""

    __tablename__ = "golden_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_field: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)


# -----------------------------------------------------------------------------
# Review-response application + session persistence
# (ported from src/persistence/sessions.py)
# -----------------------------------------------------------------------------


def apply_review_response(mappings: list[dict], response: Any) -> list[dict]:
    """Merge the client's HITL ``response`` payload into the mapping list.

    Verbatim port of ``src/persistence/sessions.py::apply_review_response``.
    Operates on (and returns) ``list[dict]`` because the HITL payload going
    over the wire is dict-shaped. The caller is responsible for converting
    back to :class:`ProposedMapping` before writing to state.
    """
    updated = [dict(m) for m in mappings]
    if not isinstance(response, dict):
        return updated

    approved_all = response.get("approved", True)
    review_map = {
        r["source_field"]: r for r in (response.get("reviews") or []) if isinstance(r, dict) and "source_field" in r
    }

    for i, m in enumerate(updated):
        src = m.get("source_field", "")
        if src in review_map:
            rev = review_map[src]
            updated[i] = {**m, "status": rev.get("status", "human_approved")}
            if "destination_field" in rev:
                dest = rev.get("destination_field")
                updated[i]["destination_field"] = dest if dest else None
        elif approved_all and m.get("status") in {"needs_review", "unmatched"}:
            updated[i] = {**m, "status": "human_approved"}

    return updated


def _has_destination(mapping) -> bool:
    """True if a :class:`ProposedMapping` has a non-empty destination_field."""
    dest = mapping.destination_field
    return bool(dest and str(dest).strip())


async def persist_session(state, session_maker, kind: str) -> dict[str, Any]:
    """Persist a finished mapping run + its field mappings to Postgres.

    Args:
        state: The current :class:`GlobalAgentState`. Read by attribute
            access (was ``state.get(...)`` against the old TypedDict).
        session_maker: An async sessionmaker (from :mod:`app.agents.core.deps`).
        kind: Either ``"canonical"`` or ``"projection"``; controls the
            ``destination_type`` recorded and whether
            ``canonical_session_id`` gets backfilled.

    Returns:
        A dict with the newly-created ``session_id`` and (for canonical
        runs) ``canonical_session_id``.
    """
    async with session_maker() as db:
        customer_id = state.customer_id or 1
        customer = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
        if not customer:
            customer = Customer(id=customer_id, name="Default", salesforce_org_id="default")
            db.add(customer)
            await db.flush()

        dest_type = state.destination_type or ""
        if kind == "canonical":
            dest_type = "canonical"

        source_value = state.source.value if state.source else "salesforce"
        ms = MappingSession(
            customer_id=customer_id,
            source=source_value,
            source_object=state.source_object or "",
            destination_type=dest_type,
            status="completed",
            mapping_kind=kind,
            canonical_session_id=state.canonical_session_id if kind == "projection" else None,
        )
        db.add(ms)
        await db.flush()

        for m in state.mappings or []:
            if not _has_destination(m):
                continue
            db.add(
                FieldMapping(
                    session_id=ms.id,
                    source_field=m.source_field,
                    destination_field=m.destination_field,
                    confidence=float(m.confidence or 0.0),
                    status=m.status.value if hasattr(m.status, "value") else str(m.status),
                    reasoning=m.reasoning or "",
                    transformation=m.transformation_needed,
                    validation_status=(
                        m.validation_status.value
                        if hasattr(m.validation_status, "value")
                        else str(m.validation_status)
                    ),
                    validation_notes=list(m.validation_notes or []),
                )
            )

        await db.commit()

    result: dict[str, Any] = {"session_id": ms.id}
    if kind == "canonical":
        result["canonical_session_id"] = ms.id
    return result


# -----------------------------------------------------------------------------
# FeedbackLearningAgent (ported from src/pipeline/feedback_learner.py)
# -----------------------------------------------------------------------------


class FeedbackLearningAgent:
    """Stores embeddings + golden rules for human-approved/corrected mappings.

    Verbatim port of ``src/pipeline/feedback_learner.py``. The original
    spun up its own async engine; we now accept an injected
    :class:`async_sessionmaker` so :mod:`app.agents.core.deps` owns the
    engine lifecycle.
    """

    def __init__(
        self,
        settings: _AgentSettingsProxy,
        openai_service: OpenAIService,
        vector_store: VectorStoreService,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Cache settings + service handles + the shared session maker."""
        self.settings = settings
        self.openai_service = openai_service
        self.vector_store = vector_store
        self.session_maker = session_maker

    async def run(self, state):
        """Persist embeddings + golden rules for human-touched mappings."""
        if not state.session_id:
            return state

        async with self.session_maker() as session:
            for mapping in state.mappings:
                if mapping.status not in {MappingStatus.human_approved, MappingStatus.human_corrected}:
                    continue

                statement = select(FieldMapping).where(
                    FieldMapping.session_id == state.session_id,
                    FieldMapping.source_field == mapping.source_field,
                )
                db_mapping = (await session.execute(statement)).scalar_one_or_none()
                if not db_mapping:
                    continue

                emb_input = f"{mapping.source_field}::{mapping.destination_field or ''}"
                embedding = (await self.openai_service.embed_texts([emb_input]))[0]
                await self.vector_store.upsert_embedding(
                    field_mapping_id=db_mapping.id,
                    embedding=embedding,
                    metadata={
                        "destination_type": state.destination_type,
                        "source_field": mapping.source_field,
                    },
                )

                if mapping.destination_field:
                    await self._upsert_golden_rule(
                        session=session,
                        source_pattern=mapping.source_field.lower(),
                        destination_field=mapping.destination_field,
                        destination_type=state.destination_type,
                    )

            await session.commit()
        return state

    async def _upsert_golden_rule(
        self,
        session: AsyncSession,
        source_pattern: str,
        destination_field: str,
        destination_type: str,
    ) -> None:
        statement = select(GoldenRule).where(
            GoldenRule.source_pattern == source_pattern,
            GoldenRule.destination_field == destination_field,
            GoldenRule.destination_type == destination_type,
        )
        rule = (await session.execute(statement)).scalar_one_or_none()
        if rule:
            rule.occurrence_count += 1
            return
        session.add(
            GoldenRule(
                source_pattern=source_pattern,
                destination_field=destination_field,
                destination_type=destination_type,
                occurrence_count=1,
            )
        )
