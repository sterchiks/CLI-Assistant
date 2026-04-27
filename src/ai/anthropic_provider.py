"""Провайдер Anthropic Claude."""

import logging
from typing import AsyncGenerator, Optional

from .provider import BaseProvider

logger = logging.getLogger(__name__)

ANTHROPIC_MODELS = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-opus-4-0",
    "claude-sonnet-4-0",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
]

DEFAULT_SYSTEM_PROMPT = """Ты — CLI Assistant, AI-ассистент для управления системой через терминал.

Правила работы:
1. Всегда объясняй что делаешь ПЕРЕД выполнением действия
2. Предупреждай о потенциально опасных операциях и объясняй риски
3. Никогда не выполняй rm -rf / или аналоги без явного подтверждения
4. Создавай бэкапы перед редактированием важных системных файлов
5. Если просят что-то опасное — объясни риски и предложи безопасную альтернативу
6. Отвечай на языке пользователя (русский или английский)
7. Будь конкретным и точным в описании действий
8. При ошибках — объясняй причину и предлагай решение"""


class AnthropicProvider(BaseProvider):
    """Провайдер для Anthropic Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._client = None

    def _get_client(self):
        """Лениво создаёт клиент Anthropic."""
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def get_provider_name(self) -> str:
        return "anthropic"

    def get_available_models(self) -> list[str]:
        return ANTHROPIC_MODELS

    async def test_connection(self) -> bool:
        """Проверяет подключение к Anthropic API."""
        try:
            client = self._get_client()
            response = await client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic connection test failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """
        Отправляет сообщения в Claude API.
        Поддерживает стриминг и tool use.
        """
        try:
            client = self._get_client()

            kwargs = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "system": self._system_prompt,
                "messages": messages,
            }

            if tools:
                kwargs["tools"] = tools

            if stream:
                async for chunk in self._stream_response(client, kwargs):
                    yield chunk
            else:
                async for chunk in self._non_stream_response(client, kwargs):
                    yield chunk

        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            yield {"type": "error", "error": str(e)}

    async def _stream_response(self, client, kwargs: dict) -> AsyncGenerator[dict, None]:
        """Стриминг ответа от Claude."""
        try:
            import anthropic

            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield {"type": "text", "content": event.delta.text}
                            elif hasattr(event.delta, "partial_json"):
                                yield {"type": "tool_input_delta", "content": event.delta.partial_json}

                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    yield {
                                        "type": "tool_call_start",
                                        "tool_name": event.content_block.name,
                                        "tool_use_id": event.content_block.id,
                                    }

                        elif event.type == "message_delta":
                            if hasattr(event.delta, "stop_reason"):
                                if event.delta.stop_reason == "tool_use":
                                    # Получаем финальное сообщение для tool calls
                                    final_msg = await stream.get_final_message()
                                    for block in final_msg.content:
                                        if block.type == "tool_use":
                                            yield {
                                                "type": "tool_call",
                                                "tool_name": block.name,
                                                "tool_input": block.input,
                                                "tool_use_id": block.id,
                                            }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            yield {"type": "error", "error": str(e)}

    async def _non_stream_response(self, client, kwargs: dict) -> AsyncGenerator[dict, None]:
        """Не-стриминговый ответ от Claude."""
        try:
            response = await client.messages.create(**kwargs)

            for block in response.content:
                if block.type == "text":
                    yield {"type": "text", "content": block.text}
                elif block.type == "tool_use":
                    yield {
                        "type": "tool_call",
                        "tool_name": block.name,
                        "tool_input": block.input,
                        "tool_use_id": block.id,
                    }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Anthropic non-stream error: {e}")
            yield {"type": "error", "error": str(e)}
