"""Главный класс ассистента — оркестрирует AI и инструменты."""

import json
import logging
import os
from datetime import datetime
from typing import AsyncGenerator, Callable, Optional

from ..ai.provider_factory import ProviderFactory
from ..settings.config_manager import get_config_manager
from ..tools.sudo_manager import SudoManager
from .safety import SafetyChecker
from .tool_executor import ToolExecutor, get_tool_definitions_for_provider

logger = logging.getLogger(__name__)


class Assistant:
    """
    Главный класс ассистента.
    Управляет историей диалога, вызовами инструментов и стримингом.
    """

    def __init__(self) -> None:
        self._config_manager = get_config_manager()
        self._config = self._config_manager.config
        self._provider = None
        self._sudo = SudoManager(cache_minutes=self._config.session.sudo_cache_minutes)
        self._safety = SafetyChecker(self._config)
        self._executor = ToolExecutor(self._safety, self._sudo)
        self._messages: list[dict] = []
        self._cwd: str = os.path.expanduser("~")

        # Callbacks для UI
        self._on_text: Optional[Callable[[str], None]] = None
        self._on_tool_start: Optional[Callable[[str, dict], None]] = None
        self._on_tool_done: Optional[Callable[[str, object, float], None]] = None
        self._on_confirm: Optional[Callable[[str, str], bool]] = None
        self._on_sudo_request: Optional[Callable[[], str]] = None

    def set_ui_callbacks(
        self,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, dict], None]] = None,
        on_tool_done: Optional[Callable[[str, object, float], None]] = None,
        on_confirm: Optional[Callable[[str, str], bool]] = None,
        on_sudo_request: Optional[Callable[[], str]] = None,
    ) -> None:
        """Устанавливает callbacks для взаимодействия с UI."""
        self._on_text = on_text
        self._on_tool_start = on_tool_start
        self._on_tool_done = on_tool_done
        self._on_confirm = on_confirm
        self._on_sudo_request = on_sudo_request

        self._executor.set_callbacks(on_start=on_tool_start, on_done=on_tool_done)
        if on_confirm:
            self._safety.set_confirm_callback(on_confirm)
        if on_sudo_request:
            self._sudo.set_password_callback(on_sudo_request)

    def reload_config(self) -> None:
        """Перезагружает конфигурацию и пересоздаёт провайдер."""
        self._config_manager.reload()
        self._config = self._config_manager.config
        self._provider = None
        self._safety = SafetyChecker(self._config)
        self._sudo.set_cache_minutes(self._config.session.sudo_cache_minutes)
        self._executor = ToolExecutor(self._safety, self._sudo)
        if self._on_confirm:
            self._safety.set_confirm_callback(self._on_confirm)

    def _get_provider(self):
        """Лениво создаёт провайдер."""
        if self._provider is None:
            self._provider = ProviderFactory.create_from_config(self._config)
        return self._provider

    def _get_tools(self) -> list[dict]:
        """Возвращает определения инструментов для текущего провайдера."""
        provider_name = self._config.ai.provider
        return get_tool_definitions_for_provider(provider_name)

    async def chat(self, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Обрабатывает сообщение пользователя.
        Yields события: {"type": "text"|"tool_start"|"tool_done"|"error", ...}
        """
        # Добавляем сообщение пользователя в историю
        self._messages.append({"role": "user", "content": user_message})

        provider = self._get_provider()
        if provider is None:
            yield {"type": "error", "error": "Провайдер не настроен. Используйте /settings для настройки."}
            return

        tools = self._get_tools()
        stream = self._config.ai.stream

        # Цикл обработки (может быть несколько итераций при tool use)
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            assistant_content = []
            current_text = ""
            tool_calls = []

            async for event in provider.chat(self._messages, tools=tools, stream=stream):
                event_type = event.get("type")

                if event_type == "text":
                    chunk = event["content"]
                    current_text += chunk
                    yield {"type": "text", "content": chunk}

                elif event_type == "tool_call_start":
                    yield {
                        "type": "tool_start",
                        "tool_name": event["tool_name"],
                        "tool_use_id": event.get("tool_use_id", ""),
                    }

                elif event_type == "tool_call":
                    tool_calls.append(event)

                elif event_type == "error":
                    yield {"type": "error", "error": event["error"]}
                    # Убираем последнее сообщение пользователя из истории при ошибке
                    if self._messages and self._messages[-1]["role"] == "user":
                        self._messages.pop()
                    return

                elif event_type == "done":
                    break

            # Сохраняем текст ассистента
            if current_text:
                assistant_content.append({"type": "text", "text": current_text})

            # Если нет tool calls — завершаем
            if not tool_calls:
                if assistant_content:
                    self._messages.append({"role": "assistant", "content": assistant_content or current_text})
                self._save_history()
                return

            # Добавляем tool use блоки в контент ассистента
            for tc in tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["tool_use_id"],
                    "name": tc["tool_name"],
                    "input": tc["tool_input"],
                })

            self._messages.append({"role": "assistant", "content": assistant_content})

            # Выполняем инструменты
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["tool_name"]
                tool_input = tc["tool_input"]
                tool_use_id = tc["tool_use_id"]

                yield {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_use_id": tool_use_id,
                }

                result = await self._executor.execute(tool_name, tool_input)
                result_str = self._executor.format_result(result)

                yield {
                    "type": "tool_done",
                    "tool_name": tool_name,
                    "result": result_str,
                    "tool_use_id": tool_use_id,
                }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_str,
                })

            # Добавляем результаты инструментов в историю
            self._messages.append({"role": "user", "content": tool_results})

        # Если превысили лимит итераций
        yield {"type": "error", "error": "Превышен лимит итераций инструментов"}

    def clear_history(self) -> None:
        """Очищает историю диалога."""
        self._messages = []

    def get_history(self) -> list[dict]:
        """Возвращает историю диалога."""
        return self._messages.copy()

    def export_history(self, path: str, fmt: str = "json") -> bool:
        """Экспортирует историю в файл."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            if fmt == "json":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._messages, f, ensure_ascii=False, indent=2)
            elif fmt == "md":
                with open(path, "w", encoding="utf-8") as f:
                    f.write("# CLI Assistant — История диалога\n\n")
                    for msg in self._messages:
                        role = "👤 Вы" if msg["role"] == "user" else "🤖 Ассистент"
                        content = msg["content"]
                        if isinstance(content, list):
                            text_parts = [
                                p.get("text", "") for p in content
                                if isinstance(p, dict) and p.get("type") == "text"
                            ]
                            content = "\n".join(text_parts)
                        f.write(f"## {role}\n\n{content}\n\n---\n\n")
            return True
        except Exception as e:
            logger.error(f"export_history error: {e}")
            return False

    def _save_history(self) -> None:
        """Сохраняет историю в файл если включено в настройках."""
        if not self._config.session.save_history:
            return
        try:
            history_path = os.path.expanduser(self._config.session.history_file)
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            # Ограничиваем размер истории
            messages = self._messages[-self._config.session.max_history:]
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"_save_history error: {e}")

    def load_history(self) -> None:
        """Загружает историю из файла."""
        if not self._config.session.save_history:
            return
        try:
            history_path = os.path.expanduser(self._config.session.history_file)
            if os.path.exists(history_path):
                with open(history_path, "r", encoding="utf-8") as f:
                    self._messages = json.load(f)
        except Exception as e:
            logger.error(f"load_history error: {e}")

    @property
    def cwd(self) -> str:
        return self._cwd

    @cwd.setter
    def cwd(self, path: str) -> None:
        expanded = os.path.expanduser(path)
        if os.path.isdir(expanded):
            self._cwd = expanded
        else:
            raise ValueError(f"Директория не существует: {path}")

    @property
    def sudo_manager(self) -> SudoManager:
        return self._sudo

    async def test_provider(self) -> bool:
        """Тестирует подключение к провайдеру."""
        provider = self._get_provider()
        if provider is None:
            return False
        return await provider.test_connection()
