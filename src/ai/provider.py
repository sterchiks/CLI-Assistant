"""Базовый класс AI провайдера."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class BaseProvider(ABC):
    """Абстрактный базовый класс для всех AI провайдеров."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """
        Отправляет сообщения и возвращает ответ.

        Yields dict с полями:
          - type: "text" | "tool_call" | "tool_result" | "done" | "error"
          - content: str (для text)
          - tool_name: str (для tool_call)
          - tool_input: dict (для tool_call)
          - tool_use_id: str (для tool_call)
          - error: str (для error)
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Проверяет подключение к API. Возвращает True если успешно."""
        ...

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Возвращает список доступных моделей."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Возвращает имя провайдера."""
        ...
