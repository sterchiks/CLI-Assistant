"""Главный интерфейс чата CLI Assistant на Textual."""

import asyncio
import os
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button, Footer, Header, Input, Label,
    Static, RichLog, LoadingIndicator
)
from textual.worker import Worker, WorkerState
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

from ..core.assistant import Assistant
from ..settings.config_manager import get_config_manager
from .themes import get_theme


# ─── Виджеты сообщений ────────────────────────────────────────────────────────

class UserMessage(Static):
    """Пузырь сообщения пользователя (выровнен вправо)."""

    def __init__(self, text: str, timestamp: str = "") -> None:
        content = f"[bold cyan]{text}[/bold cyan]"
        if timestamp:
            content += f"\n[dim]{timestamp}  👤 Вы[/dim]"
        super().__init__(content, classes="user-bubble")


class AssistantMessage(Static):
    """Пузырь сообщения ассистента (выровнен влево)."""

    def __init__(self, timestamp: str = "") -> None:
        ts = f"[dim]🤖 Ассистент  {timestamp}[/dim]\n" if timestamp else "[dim]🤖 Ассистент[/dim]\n"
        super().__init__(ts, classes="assistant-bubble", id="current-assistant-msg")
        self._text = ts

    def append_text(self, chunk: str) -> None:
        self._text += chunk
        self.update(self._text)

    def finalize(self) -> None:
        self.remove_id()

    def remove_id(self) -> None:
        try:
            self.id = None
        except Exception:
            pass


class ToolCallWidget(Static):
    """Виджет отображения вызова инструмента."""

    def __init__(self, tool_name: str, tool_input: dict) -> None:
        params = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(tool_input.items())[:3])
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{tool_name}[/cyan]\n"
            f"[dim]{params}[/dim]\n"
            f"[yellow]⏳ Выполняю...[/yellow]"
        )
        super().__init__(content, classes="tool-call", id=f"tool-{id(self)}")
        self._tool_name = tool_name

    def set_done(self, elapsed: float) -> None:
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{self._tool_name}[/cyan]\n"
            f"[green]✅ Готово за {elapsed:.2f}с[/green]"
        )
        self.update(content)

    def set_error(self, error: str) -> None:
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{self._tool_name}[/cyan]\n"
            f"[red]❌ Ошибка: {error[:80]}[/red]"
        )
        self.update(content)


class ConfirmDialog(Static):
    """Диалог подтверждения опасного действия."""

    def __init__(self, action: str, target: str, callback) -> None:
        content = (
            f"[bold yellow]⚠️  ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЯ[/bold yellow]\n\n"
            f"[white]{action}[/white]\n"
            f"[cyan]{target[:60]}[/cyan]\n\n"
            f"Продолжить? [[bold green]Y[/bold green]/[bold red]n[/bold red]]"
        )
        super().__init__(content, classes="confirm-dialog")
        self._callback = callback

    async def confirm(self, yes: bool) -> None:
        await self._callback(yes)
        self.remove()


class SudoPasswordDialog(Container):
    """Диалог ввода пароля sudo."""

    def __init__(self, callback) -> None:
        super().__init__(id="sudo-dialog")
        self._callback = callback

    def compose(self) -> ComposeResult:
        yield Static("[bold yellow]🔐 Требуется пароль sudo[/bold yellow]", id="sudo-title")
        yield Input(placeholder="Введите пароль sudo...", password=True, id="sudo-input")
        yield Horizontal(
            Button("Подтвердить", id="btn-sudo-ok", variant="primary"),
            Button("Отмена", id="btn-sudo-cancel"),
            id="sudo-buttons",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sudo-ok":
            password = self.query_one("#sudo-input", Input).value
            self.remove()
            await self._callback(password)
        elif event.button.id == "btn-sudo-cancel":
            self.remove()
            await self._callback("")

    CSS = """
    #sudo-dialog {
        background: #1a2744;
        border: round #ff9800;
        padding: 1 2;
        margin: 1 2;
        height: auto;
    }
    #sudo-title { color: #ff9800; margin-bottom: 1; }
    #sudo-buttons { margin-top: 1; }
    #sudo-buttons Button { margin-right: 1; }
    """


# ─── Боковая панель ───────────────────────────────────────────────────────────

class SidebarWidget(Static):
    """Боковая панель с системной информацией."""

    cpu: reactive[float] = reactive(0.0)
    ram_used: reactive[str] = reactive("—")
    ram_total: reactive[str] = reactive("—")
    disk_used: reactive[str] = reactive("—")
    disk_total: reactive[str] = reactive("—")
    last_actions: reactive[list] = reactive([])

    def render(self) -> str:
        actions_str = "\n".join(
            f"  [green]✓[/green] {a}" for a in self.last_actions[-5:]
        ) or "  [dim]нет действий[/dim]"

        return (
            f"[bold cyan]СИСТЕМА[/bold cyan]\n"
            f"CPU: [yellow]{self.cpu:.0f}%[/yellow]\n"
            f"RAM: [yellow]{self.ram_used}/{self.ram_total}[/yellow]\n"
            f"Диск: [yellow]{self.disk_used}/{self.disk_total}[/yellow]\n"
            f"\n[bold cyan]ДЕЙСТВИЯ[/bold cyan]\n"
            f"{actions_str}\n"
            f"\n[bold cyan]ПУТЬ[/bold cyan]\n"
            f"[dim]{self.app.assistant.cwd[:18]}[/dim]"
        )

    def update_system_info(self, info: dict) -> None:
        self.cpu = info.get("cpu_percent", 0.0)
        self.ram_used = info.get("ram_used_human", "—")
        self.ram_total = info.get("ram_total_human", "—")
        self.disk_used = info.get("disk_used_human", "—")
        self.disk_total = info.get("disk_total_human", "—")

    def add_action(self, action: str) -> None:
        actions = list(self.last_actions)
        actions.append(action[:20])
        self.last_actions = actions[-10:]


# ─── Главное приложение ───────────────────────────────────────────────────────

class CLIAssistantApp(App):
    """Главное TUI приложение CLI Assistant."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Выход"),
        Binding("ctrl+s", "open_settings", "Настройки"),
        Binding("ctrl+l", "clear_chat", "Очистить"),
        Binding("ctrl+h", "show_help", "Помощь"),
        Binding("escape", "cancel_input", "Отмена"),
    ]

    show_sidebar: reactive[bool] = reactive(True)
    is_thinking: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self._config_manager = get_config_manager()
        self._config = self._config_manager.config
        self.assistant = Assistant()
        self._current_assistant_widget: Optional[AssistantMessage] = None
        self._current_tool_widget: Optional[ToolCallWidget] = None
        self._pending_confirm: Optional[asyncio.Future] = None
        self._pending_sudo: Optional[asyncio.Future] = None
        self._setup_assistant_callbacks()

    def _setup_assistant_callbacks(self) -> None:
        """Подключает callbacks ассистента к UI."""
        self.assistant.set_ui_callbacks(
            on_confirm=self._on_confirm_request,
            on_sudo_request=self._on_sudo_request,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with ScrollableContainer(id="chat-area"):
                yield Static(
                    "[dim]🤖 CLI Assistant готов к работе. Введите сообщение или /help[/dim]",
                    id="chat-placeholder"
                )
            yield SidebarWidget(id="sidebar")
        with Container(id="input-area"):
            yield Input(
                placeholder="Введите сообщение или /команду...",
                id="message-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Инициализация при запуске."""
        theme_css = get_theme(self._config.ui.theme)
        self.stylesheet.add_css(theme_css)
        self._update_header()
        # Запускаем периодическое обновление системной информации
        self.set_interval(5.0, self._refresh_system_info)
        self._refresh_system_info()
        # Адаптируем layout под размер терминала
        self._adapt_layout()

    def on_resize(self) -> None:
        """Адаптируем layout при изменении размера."""
        self._adapt_layout()

    def _adapt_layout(self) -> None:
        """Скрываем боковую панель при узком терминале."""
        try:
            sidebar = self.query_one("#sidebar", SidebarWidget)
            if self.size.width < 100:
                sidebar.display = False
            else:
                sidebar.display = True
        except Exception:
            pass

    def _update_header(self) -> None:
        """Обновляет заголовок с информацией о провайдере."""
        try:
            provider = self._config.ai.provider
            model = self._config.ai.model
            self.title = f"🤖 CLI Assistant | {provider}: {model}"
            self.sub_title = self.assistant.cwd
        except Exception:
            self.title = "🤖 CLI Assistant"

    def _refresh_system_info(self) -> None:
        """Обновляет системную информацию в боковой панели."""
        try:
            from ..tools.terminal_manager import TerminalManager
            tm = TerminalManager()
            info = tm.get_system_info()
            sidebar = self.query_one("#sidebar", SidebarWidget)
            sidebar.update_system_info(info)
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Обрабатывает отправку сообщения."""
        if event.input.id != "message-input":
            return

        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        # Обрабатываем slash-команды
        if text.startswith("/"):
            await self._handle_slash_command(text)
            return

        # Отправляем сообщение ассистенту
        await self._send_message(text)

    async def _send_message(self, text: str) -> None:
        """Отправляет сообщение ассистенту и отображает ответ."""
        if self.is_thinking:
            return

        # Убираем placeholder
        try:
            self.query_one("#chat-placeholder").remove()
        except Exception:
            pass

        # Добавляем сообщение пользователя
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        ts = datetime.now().strftime("%H:%M")
        user_widget = UserMessage(text, ts)
        await chat_area.mount(user_widget)

        # Создаём виджет ответа ассистента
        self.is_thinking = True
        assistant_widget = AssistantMessage(ts)
        self._current_assistant_widget = assistant_widget
        await chat_area.mount(assistant_widget)
        chat_area.scroll_end(animate=False)

        # Запускаем обработку в worker
        self.run_worker(self._process_message(text), exclusive=True)

    async def _process_message(self, text: str) -> None:
        """Worker: обрабатывает сообщение через ассистента."""
        try:
            async for event in self.assistant.chat(text):
                event_type = event.get("type")

                if event_type == "text":
                    chunk = event["content"]
                    if self._current_assistant_widget:
                        self.call_from_thread(
                            self._current_assistant_widget.append_text, chunk
                        )

                elif event_type == "tool_start":
                    tool_name = event.get("tool_name", "")
                    tool_input = event.get("tool_input", {})
                    if self._config.ui.show_tool_calls:
                        self.call_from_thread(
                            self._add_tool_widget, tool_name, tool_input
                        )

                elif event_type == "tool_done":
                    tool_name = event.get("tool_name", "")
                    if self._current_tool_widget:
                        self.call_from_thread(
                            self._current_tool_widget.set_done, 0.0
                        )
                    sidebar = self.query_one("#sidebar", SidebarWidget)
                    self.call_from_thread(sidebar.add_action, tool_name)

                elif event_type == "error":
                    error = event.get("error", "Неизвестная ошибка")
                    self.call_from_thread(self._show_error, error)

        except Exception as e:
            self.call_from_thread(self._show_error, str(e))
        finally:
            self.call_from_thread(self._finish_response)

    def _add_tool_widget(self, tool_name: str, tool_input: dict) -> None:
        """Добавляет виджет вызова инструмента в чат."""
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            widget = ToolCallWidget(tool_name, tool_input)
            self._current_tool_widget = widget
            self.call_later(chat_area.mount, widget)
            self.call_later(chat_area.scroll_end, False)
        except Exception:
            pass

    def _show_error(self, error: str) -> None:
        """Показывает сообщение об ошибке в чате."""
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            error_widget = Static(
                f"[bold red]❌ Ошибка:[/bold red] {error}",
                classes="error-message"
            )
            self.call_later(chat_area.mount, error_widget)
        except Exception:
            pass

    def _finish_response(self) -> None:
        """Завершает отображение ответа."""
        self.is_thinking = False
        self._current_assistant_widget = None
        self._current_tool_widget = None
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            chat_area.scroll_end(animate=False)
        except Exception:
            pass

    async def _on_confirm_request(self, action: str, target: str) -> bool:
        """Callback для запроса подтверждения от UI."""
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending_confirm = future

        def show_dialog():
            try:
                chat_area = self.query_one("#chat-area", ScrollableContainer)
                dialog = ConfirmDialog(action, target, lambda yes: future.set_result(yes))
                self.call_later(chat_area.mount, dialog)
            except Exception:
                future.set_result(False)

        self.call_from_thread(show_dialog)
        return await future

    async def _on_sudo_request(self) -> str:
        """Callback для запроса пароля sudo от UI."""
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self._pending_sudo = future

        def show_sudo_dialog():
            try:
                chat_area = self.query_one("#chat-area", ScrollableContainer)
                dialog = SudoPasswordDialog(lambda pwd: future.set_result(pwd))
                self.call_later(chat_area.mount, dialog)
            except Exception:
                future.set_result("")

        self.call_from_thread(show_sudo_dialog)
        return await future

    # ─── Slash-команды ────────────────────────────────────────────────────────

    async def _handle_slash_command(self, text: str) -> None:
        """Обрабатывает slash-команды."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        chat_area = self.query_one("#chat-area", ScrollableContainer)

        try:
            self.query_one("#chat-placeholder").remove()
        except Exception:
            pass

        if cmd == "/help":
            await chat_area.mount(Static(HELP_TEXT, classes="assistant-bubble"))

        elif cmd == "/clear":
            self.assistant.clear_history()
            await self._clear_chat_widgets()
            await chat_area.mount(Static("[dim]История очищена[/dim]"))

        elif cmd == "/provider":
            if arg:
                self._config.ai.provider = arg
                get_config_manager().save()
                self.assistant.reload_config()
                await chat_area.mount(Static(f"[green]Провайдер изменён на: {arg}[/green]"))
            else:
                await chat_area.mount(Static(f"[cyan]Текущий провайдер: {self._config.ai.provider}[/cyan]"))

        elif cmd == "/model":
            if arg:
                self._config.ai.model = arg
                get_config_manager().save()
                self.assistant.reload_config()
                self._update_header()
                await chat_area.mount(Static(f"[green]Модель изменена на: {arg}[/green]"))
            else:
                await chat_area.mount(Static(f"[cyan]Текущая модель: {self._config.ai.model}[/cyan]"))

        elif cmd == "/theme":
            if arg:
                self._config.ui.theme = arg
                get_config_manager().save()
                theme_css = get_theme(arg)
                self.stylesheet.add_css(theme_css)
                await chat_area.mount(Static(f"[green]Тема изменена на: {arg}[/green]"))
            else:
                from .themes import get_theme_names
                themes = ", ".join(get_theme_names())
                await chat_area.mount(Static(f"[cyan]Доступные темы: {themes}[/cyan]"))

        elif cmd == "/apikey":
            await chat_area.mount(Static("[yellow]Введите новый API ключ:[/yellow]"))
            # Показываем диалог ввода пароля
            future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
            dialog = SudoPasswordDialog(lambda v: future.set_result(v))
            await chat_area.mount(dialog)
            key = await future
            if key:
                get_config_manager().set_api_key(key)
                self.assistant.reload_config()
                await chat_area.mount(Static("[green]API ключ обновлён[/green]"))

        elif cmd == "/baseurl":
            if arg:
                self._config.ai.base_url = arg
                get_config_manager().save()
                self.assistant.reload_config()
                await chat_area.mount(Static(f"[green]Base URL изменён на: {arg}[/green]"))

        elif cmd == "/cd":
            if arg:
                try:
                    self.assistant.cwd = arg
                    self.sub_title = self.assistant.cwd
                    await chat_area.mount(Static(f"[green]Рабочая директория: {self.assistant.cwd}[/green]"))
                except ValueError as e:
                    await chat_area.mount(Static(f"[red]{e}[/red]", classes="error-message"))

        elif cmd == "/ls":
            from ..tools.file_reader import FileReader
            fr = FileReader()
            items = fr.list_directory(self.assistant.cwd, show_hidden=False, recursive=False)
            lines = "\n".join(
                f"  {'📁' if i.get('is_dir') else '📄'} {i['name']}"
                for i in (items if isinstance(items, list) else [])
            )
            await chat_area.mount(Static(f"[cyan]{self.assistant.cwd}[/cyan]\n{lines or '(пусто)'}"))

        elif cmd == "/history":
            history = self.assistant.get_history()
            count = len([m for m in history if m["role"] == "user"])
            await chat_area.mount(Static(f"[cyan]Сообщений в истории: {count}[/cyan]"))

        elif cmd == "/export":
            path = arg or os.path.expanduser("~/cli-assistant-history.json")
            fmt = "md" if path.endswith(".md") else "json"
            ok = self.assistant.export_history(path, fmt)
            if ok:
                await chat_area.mount(Static(f"[green]История экспортирована: {path}[/green]"))
            else:
                await chat_area.mount(Static(f"[red]Ошибка экспорта[/red]", classes="error-message"))

        elif cmd == "/sudo":
            if arg == "clear":
                self.assistant.sudo_manager.clear_sudo_cache()
                await chat_area.mount(Static("[green]Кэш sudo очищен[/green]"))
            else:
                ok = await self.assistant.sudo_manager.request_sudo_password()
                if ok:
                    remaining = self.assistant.sudo_manager.get_cache_remaining_seconds()
                    await chat_area.mount(Static(f"[green]Sudo активирован на {remaining}с[/green]"))
                else:
                    await chat_area.mount(Static("[red]Не удалось получить пароль sudo[/red]"))

        elif cmd == "/settings":
            await self.action_open_settings()

        else:
            await chat_area.mount(Static(
                f"[yellow]Неизвестная команда: {cmd}. Введите /help для справки.[/yellow]"
            ))

        chat_area.scroll_end(animate=False)

    async def _clear_chat_widgets(self) -> None:
        """Удаляет все виджеты из области чата."""
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        for child in list(chat_area.children):
            child.remove()

    # ─── Actions ──────────────────────────────────────────────────────────────

    async def action_open_settings(self) -> None:
        """Открывает экран настроек."""
        from .settings_screen import SettingsScreen
        await self.push_screen(SettingsScreen())

    async def action_clear_chat(self) -> None:
        """Очищает чат."""
        self.assistant.clear_history()
        await self._clear_chat_widgets()
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        await chat_area.mount(Static("[dim]История очищена[/dim]"))

    async def action_show_help(self) -> None:
        """Показывает справку."""
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        await chat_area.mount(Static(HELP_TEXT, classes="assistant-bubble"))
        chat_area.scroll_end(animate=False)

    def action_cancel_input(self) -> None:
        """Сбрасывает поле ввода."""
        try:
            self.query_one("#message-input", Input).value = ""
        except Exception:
            pass

    CSS = """
    #main-layout {
        height: 1fr;
    }

    #chat-area {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }

    #sidebar {
        width: 22;
        height: 1fr;
        padding: 1;
        border-left: solid #2a2a4a;
    }

    #input-area {
        height: 3;
        padding: 0 1;
    }

    #message-input {
        width: 1fr;
        height: 3;
    }

    .user-bubble {
        background: #0f3460;
        color: #e0e0e0;
        border: round #3a5a8a;
        margin: 1 2;
        padding: 1 2;
        width: auto;
        max-width: 70%;
        align-horizontal: right;
    }

    .assistant-bubble {
        background: #1e3a2f;
        color: #e0e0e0;
        border: round #2a5a3a;
        margin: 1 2;
        padding: 1 2;
        width: auto;
        max-width: 85%;
    }

    .tool-call {
        background: #1a2744;
        color: #88aaff;
        border: solid #3a4a7a;
        margin: 0 4;
        padding: 0 1;
        width: auto;
    }

    .error-message {
        color: #f44336;
        background: #3a1a1a;
        border: solid #f44336;
        margin: 1 2;
        padding: 1;
    }

    .confirm-dialog {
        background: #2a1a00;
        border: round #ff9800;
        margin: 1 2;
        padding: 1 2;
    }
    """


HELP_TEXT = """[bold cyan]📖 Справка CLI Assistant[/bold cyan]

[bold]Slash-команды:[/bold]
  [cyan]/help[/cyan]              — эта справка
  [cyan]/settings[/cyan]          — открыть настройки
  [cyan]/provider [name][/cyan]   — сменить провайдера (anthropic/gemini/openai_compatible)
  [cyan]/model [name][/cyan]      — сменить модель
  [cyan]/theme [name][/cyan]      — сменить тему (dark/light/cyberpunk/nord/solarized)
  [cyan]/apikey[/cyan]            — изменить API ключ
  [cyan]/baseurl [url][/cyan]     — изменить base URL
  [cyan]/clear[/cyan]             — очистить историю чата
  [cyan]/history[/cyan]           — показать статистику истории
  [cyan]/export [path][/cyan]     — экспортировать историю (json/md)
  [cyan]/cd [path][/cyan]         — сменить рабочую директорию
  [cyan]/ls[/cyan]                — содержимое текущей директории
  [cyan]/sudo[/cyan]              — запросить sudo пароль
  [cyan]/sudo clear[/cyan]        — очистить кэш sudo

[bold]Горячие клавиши:[/bold]
  [cyan]Ctrl+C[/cyan]  — выход
  [cyan]Ctrl+S[/cyan]  — настройки
  [cyan]Ctrl+L[/cyan]  — очистить чат
  [cyan]Ctrl+H[/cyan]  — справка
  [cyan]Enter[/cyan]   — отправить сообщение"""
