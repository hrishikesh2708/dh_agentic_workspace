"""pgvector store for mapping examples + corrections.

Ported from ``crawler_agent/src/integrations/vector_store.py``. Tables it
reads/writes (``mapping_embeddings``, ``field_mappings``, ``mapping_sessions``)
are added by Stage 2's Alembic migration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.core.agent_config import _AgentSettingsProxy


class VectorStoreService:
    """Async pgvector access for top-k example retrieval + correction embeddings."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Build the async SQLAlchemy engine.

        Args:
            settings: Agent settings proxy providing ``database_url``.
        """
        self.settings = settings
        self.engine = create_async_engine(settings.database_url, echo=False, future=True)

    async def search_examples(
        self,
        embedding: list[float],
        destination_type: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Find the ``top_k`` past field mappings most similar to ``embedding``.

        Args:
            embedding: Query embedding vector.
            destination_type: Restricts search to mappings for this destination.
            top_k: Number of examples to return.

        Returns:
            List of dicts with ``source_field``, ``destination_field``,
            ``reasoning``, and ``metadata``.
        """
        query = text(
            """
            SELECT fm.source_field, fm.destination_field, fm.reasoning, me.metadata
            FROM mapping_embeddings me
            JOIN field_mappings fm ON fm.id = me.field_mapping_id
            JOIN mapping_sessions ms ON ms.id = fm.session_id
            WHERE ms.destination_type = :destination_type
            ORDER BY me.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        )
        async with self.engine.begin() as connection:
            result = await connection.execute(
                query,
                {"destination_type": destination_type, "embedding": str(embedding), "top_k": top_k},
            )
            rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

    async def upsert_embedding(
        self,
        field_mapping_id: int,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """Insert or replace the embedding for a given field mapping.

        Args:
            field_mapping_id: PK of the ``field_mappings`` row.
            embedding: Embedding vector for the source→destination pair.
            metadata: Arbitrary JSON metadata stored alongside.
        """
        query = text(
            """
            INSERT INTO mapping_embeddings (field_mapping_id, embedding, metadata)
            VALUES (:field_mapping_id, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
            ON CONFLICT (field_mapping_id)
            DO UPDATE SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata
            """
        )
        async with self.engine.begin() as connection:
            await connection.execute(
                query,
                {
                    "field_mapping_id": field_mapping_id,
                    "embedding": str(embedding),
                    "metadata": str(metadata).replace("'", '"'),
                },
            )
