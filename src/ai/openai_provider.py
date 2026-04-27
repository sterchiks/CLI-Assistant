"""Провайдер OpenAI-совместимых API."""

import logging
from typing import AsyncGenerator, Optional

from .provider import BaseProvider

logger = logging.getLogger(__name__)

OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]

KNOWN_PROVIDERS = {
    "openai": {"base_url": "https://api.openai.com/v1", "models": OPENAI_MODELS},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]},
    "ollama": {"base_url": "http://localhost:11434/v1", "models": ["llama3", "mistral", "codellama"]},
    "lmstudio": {"base_url": "http://localhost:1234/v1", "models": []},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "models": []},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "models": ["mistral-large-latest", "mistral-small-latest"]},
    "together": {"base_url": "https://api.together.xyz/v1", "models": []},
}

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


class OpenAICompatibleProvider(BaseProvider):
    """Провайдер для OpenAI-совместимых API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or "https://api.openai.com/v1"
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._client = None

    def _get_client(self):
        """Лениво создаёт клиент OpenAI."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    def get_provider_name(self) -> str:
        return "openai_compatible"

    def get_available_models(self) -> list[str]:
        return OPENAI_MODELS

    async def test_connection(self) -> bool:
        """Проверяет подключение к API."""
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return bool(response.choices)
        except Exception as e:
            logger.error(f"OpenAI-compatible connection test failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """Отправляет сообщения в OpenAI-совместимый API."""
        try:
            client = self._get_client()

            # Добавляем системный промпт
            full_messages = [{"role": "system", "content": self._system_prompt}] + messages

            kwargs = {
                "model": self._model,
                "messages": full_messages,
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
                "stream": stream,
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            if stream:
                async for chunk in self._stream_response(client, kwargs):
                    yield chunk
            else:
                async for chunk in self._non_stream_response(client, kwargs):
                    yield chunk

        except Exception as e:
            logger.error(f"OpenAI-compatible chat error: {e}")
            yield {"type": "error", "error": str(e)}

    async def _stream_response(self, client, kwargs: dict) -> AsyncGenerator[dict, None]:
        """Стриминг ответа."""
        try:
            import json as json_module
            tool_calls_buffer: dict[int, dict] = {}

            async with await client.chat.completions.create(**kwargs) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Текстовый контент
                    if delta.content:
                        yield {"type": "text", "content": delta.content}

                    # Tool calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc.id:
                                tool_calls_buffer[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_buffer[idx]["name"] = tc.function.name
                                    yield {
                                        "type": "tool_call_start",
                                        "tool_name": tc.function.name,
                                        "tool_use_id": tc.id or f"tc_{idx}",
                                    }
                                if tc.function.arguments:
                                    tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                    # Финализируем tool calls при завершении
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                    if finish_reason == "tool_calls":
                        for idx, tc_data in tool_calls_buffer.items():
                            try:
                                args = json_module.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            except json_module.JSONDecodeError:
                                args = {}
                            yield {
                                "type": "tool_call",
                                "tool_name": tc_data["name"],
                                "tool_input": args,
                                "tool_use_id": tc_data["id"],
                            }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            yield {"type": "error", "error": str(e)}

    async def _non_stream_response(self, client, kwargs: dict) -> AsyncGenerator[dict, None]:
        """Не-стриминговый ответ."""
        try:
            import json as json_module
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            if choice.message.content:
                yield {"type": "text", "content": choice.message.content}

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    try:
                        args = json_module.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json_module.JSONDecodeError:
                        args = {}
                    yield {
                        "type": "tool_call",
                        "tool_name": tc.function.name,
                        "tool_input": args,
                        "tool_use_id": tc.id,
                    }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"OpenAI non-stream error: {e}")
            yield {"type": "error", "error": str(e)}
