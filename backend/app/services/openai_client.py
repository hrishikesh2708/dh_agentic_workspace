"""OpenAI client wrapper for chat-JSON + embeddings.

Ported from ``crawler_agent/src/integrations/openai_client.py``. Only the
import path changed — behaviour is identical.
"""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.agents.agent_config import _AgentSettingsProxy


class OpenAIService:
    """Thin async wrapper exposing the two calls the mapper needs."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise the underlying OpenAI client (lazy on first call).

        Args:
            settings: Agent settings proxy providing OpenAI credentials.
        """
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: Strings to embed.

        Returns:
            A list of embedding vectors. Returns zero vectors when no API key
            is configured (so unit tests / offline mode degrade gracefully).
        """
        if not self.client:
            return [[0.0] * 1536 for _ in texts]

        response = await self.client.embeddings.create(model=self.settings.openai_embedding_model, input=texts)
        return [item.embedding for item in response.data]

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Call the chat model with JSON response_format and parse the output.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            Parsed JSON object. Returns ``{}`` when no API key is configured.
        """
        if not self.client:
            return {}

        response = await self.client.chat.completions.create(
            model=self.settings.openai_chat_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
