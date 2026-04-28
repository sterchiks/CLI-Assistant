"""Провайдер Google Gemini."""

import json
import logging
from typing import AsyncGenerator, Optional

from .provider import BaseProvider

logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

from .system_prompt import DEFAULT_SYSTEM_PROMPT


class GeminiProvider(BaseProvider):
    """Провайдер для Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
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
        """Лениво создаёт клиент Gemini."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai
        return self._client

    def get_provider_name(self) -> str:
        return "gemini"

    def get_available_models(self) -> list[str]:
        return GEMINI_MODELS

    async def test_connection(self) -> bool:
        """Проверяет подключение к Gemini API."""
        try:
            import asyncio
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(self._model)
            # Gemini SDK синхронный — запускаем в executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content("Hi", generation_config={"max_output_tokens": 10})
            )
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """
        Отправляет сообщения в Gemini API.
        Конвертирует формат сообщений из OpenAI-style в Gemini-style.
        """
        try:
            import asyncio
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)

            # Конвертируем tools в Gemini формат
            gemini_tools = None
            if tools:
                gemini_tools = self._convert_tools(tools)

            # Конвертируем историю сообщений
            history, last_message = self._convert_messages(messages)

            model_kwargs = {
                "generation_config": {
                    "temperature": self._temperature,
                    "max_output_tokens": self._max_tokens,
                },
                "system_instruction": self._system_prompt,
            }
            if gemini_tools:
                model_kwargs["tools"] = gemini_tools

            model = genai.GenerativeModel(self._model, **model_kwargs)
            chat = model.start_chat(history=history)

            if stream:
                async for chunk in self._stream_response(chat, last_message, loop=asyncio.get_event_loop()):
                    yield chunk
            else:
                async for chunk in self._non_stream_response(chat, last_message, loop=asyncio.get_event_loop()):
                    yield chunk

        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            yield {"type": "error", "error": str(e)}

    def _convert_messages(self, messages: list[dict]) -> tuple[list, str]:
        """Конвертирует сообщения в формат Gemini."""
        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            if isinstance(content, list):
                # Обрабатываем составные сообщения
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                content = " ".join(text_parts)
            history.append({"role": role, "parts": [content]})

        last = messages[-1]
        last_content = last["content"]
        if isinstance(last_content, list):
            text_parts = [p["text"] for p in last_content if p.get("type") == "text"]
            last_content = " ".join(text_parts)

        return history, last_content

    def _clean_schema(self, schema: dict) -> dict:
        """Удаляет поля JSON Schema, которые Gemini не принимает."""
        if not isinstance(schema, dict):
            return schema

        result = {}
        for key, value in schema.items():
            if key in ("default", "$schema", "additionalProperties", "examples"):
                continue
            if isinstance(value, dict):
                result[key] = self._clean_schema(value)
            elif isinstance(value, list):
                result[key] = [
                    self._clean_schema(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _convert_tools(self, tools: list[dict]) -> list:
        """Конвертирует tools из OpenAI формата в Gemini формат."""
        import google.generativeai.types as genai_types
        gemini_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                gemini_tools.append(
                    genai_types.Tool(
                        function_declarations=[
                            genai_types.FunctionDeclaration(
                                name=func["name"],
                                description=func.get("description", ""),
                                parameters=self._clean_schema(func.get("parameters", {})),
                            )
                        ]
                    )
                )
        return gemini_tools

    async def _stream_response(self, chat, message: str, loop) -> AsyncGenerator[dict, None]:
        """Стриминг ответа от Gemini."""
        try:
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(message, stream=True)
            )
            for chunk in response:
                if chunk.text:
                    yield {"type": "text", "content": chunk.text}
                # Проверяем function calls
                if hasattr(chunk, "candidates"):
                    for candidate in chunk.candidates:
                        if hasattr(candidate.content, "parts"):
                            for part in candidate.content.parts:
                                if hasattr(part, "function_call") and part.function_call:
                                    fc = part.function_call
                                    yield {
                                        "type": "tool_call",
                                        "tool_name": fc.name,
                                        "tool_input": dict(fc.args),
                                        "tool_use_id": f"gemini_{fc.name}",
                                    }
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"Gemini stream error: {e}")
            yield {"type": "error", "error": str(e)}

    async def _non_stream_response(self, chat, message: str, loop) -> AsyncGenerator[dict, None]:
        """Не-стриминговый ответ от Gemini."""
        try:
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(message)
            )
            if response.text:
                yield {"type": "text", "content": response.text}

            # Проверяем function calls
            if hasattr(response, "candidates"):
                for candidate in response.candidates:
                    if hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call") and part.function_call:
                                fc = part.function_call
                                yield {
                                    "type": "tool_call",
                                    "tool_name": fc.name,
                                    "tool_input": dict(fc.args),
                                    "tool_use_id": f"gemini_{fc.name}",
                                }
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"Gemini non-stream error: {e}")
            yield {"type": "error", "error": str(e)}
