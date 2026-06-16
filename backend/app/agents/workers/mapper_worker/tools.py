"""mapper_worker pipeline agent.

Ported verbatim from ``crawler_agent/src/pipeline/mapper.py``. Only the
import paths + the location of ``mapper_system.txt`` changed (now lives at
``app/agents/core/prompts/mapper_system.txt``).
"""

from __future__ import annotations

from pathlib import Path

from app.agents.core.agent_config import _AgentSettingsProxy
from app.agents.shared_tools.openai_client import OpenAIService
from app.agents.shared_tools.vector_store import VectorStoreService
from app.core.logging import logger
from app.schemas import ProposedMapping

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "core" / "prompts" / "mapper_system.txt"


class MapperAgent:
    """LLM-based field-mapping agent with pgvector example retrieval."""

    def __init__(
        self,
        settings: _AgentSettingsProxy,
        openai_service: OpenAIService,
        vector_store: VectorStoreService,
    ) -> None:
        """Cache settings + service handles + load the system prompt once.

        Args:
            settings: Agent settings proxy (controls top-k examples).
            openai_service: Client for embeddings + chat-JSON.
            vector_store: pgvector store for example retrieval.
        """
        self.settings = settings
        self.openai_service = openai_service
        self.vector_store = vector_store
        self.system_prompt = self._load_prompt()

    async def run(self, state):
        """Produce ``ProposedMapping`` rows from source × destination schemas."""
        if not state.source_schema or not state.destination_schema:
            raise ValueError("MapperAgent requires both source_schema and destination_schema")

        source_payload = [
            {"name": f.name, "label": f.label, "type": f.type, "description": f.description or ""}
            for f in state.source_schema.fields
        ]
        dest_payload = [
            {"name": f.name, "type": f.type, "required": f.required, "description": f.description or ""}
            for f in state.destination_schema.fields
        ]

        embedding_inputs = [
            f"{item['name']} {item['label']} {item['type']} {item['description']}".strip() for item in source_payload
        ]
        source_embeddings = await self.openai_service.embed_texts(embedding_inputs)
        retrieval_key = state.vector_search_destination_type or state.destination_type
        example_rows = await self._retrieve_examples(source_embeddings, retrieval_key)

        user_prompt = (
            f"Source fields: {source_payload}\n\n"
            f"Destination fields: {dest_payload}\n\n"
            f"Retrieved examples: {example_rows}\n\n"
            "Return JSON with key 'mappings' where each item has: source_field, destination_field, confidence, "
            "reasoning, transformation_needed."
        )
        llm_output = await self.openai_service.chat_json(self.system_prompt, user_prompt)

        proposed = []
        for item in llm_output.get("mappings", []):
            if isinstance(item, dict):
                source_field = item.get("source_field")
                if source_field is None or (
                    isinstance(source_field, str) and source_field.strip().lower() in {"", "null", "none"}
                ):
                    continue
            proposed.append(ProposedMapping.model_validate(item))

        if not proposed:
            proposed = [ProposedMapping(source_field=field["name"]) for field in source_payload]

        state.mappings = proposed
        return state

    async def _retrieve_examples(self, embeddings: list[list[float]], destination_type: str) -> list[dict]:
        rows: list[dict] = []
        try:
            for emb in embeddings[:2]:
                matches = await self.vector_store.search_examples(
                    emb, destination_type, top_k=self.settings.mapper_top_k_examples
                )
                rows.extend(matches)
        except Exception as exc:
            logger.warning(
                "mapper_example_retrieval_failed",
                destination_type=destination_type,
                error=str(exc),
            )
        return rows

    @staticmethod
    def _load_prompt() -> str:
        if not _PROMPT_PATH.exists():
            return ""
        return _PROMPT_PATH.read_text(encoding="utf-8")
