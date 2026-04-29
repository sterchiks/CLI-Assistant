"""Экран настроек внутри чата."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from ..settings.config_manager import get_config_manager
from .themes import get_theme_names


class SettingsScreen(Screen):
    """Полноэкранный TUI для изменения настроек."""

    BINDINGS = [Binding("escape", "dismiss", "Закрыть")]

    def compose(self) -> ComposeResult:
        cm = get_config_manager()
        cfg = cm.config

        provider_opts = [
            ("Anthropic (Claude)", "anthropic"),
            ("Google Gemini", "gemini"),
            ("OpenAI-совместимый", "openai_compatible"),
        ]
        theme_opts = [(t.capitalize(), t) for t in get_theme_names()]

        yield Container(
            Static("⚙️  Настройки CLI Assistant", id="settings-title"),
            Static(""),
            Static("[bold]AI Провайдер[/bold]"),
            Select(provider_opts, value=cfg.ai.provider, id="sel-provider"),
            Label("Модель:"),
            Input(value=cfg.ai.model, id="inp-model"),
            Label("Base URL (для OpenAI-совместимых):"),
            Input(value=cfg.ai.base_url or "", id="inp-baseurl"),
            Label("Температура (0.0–1.0):"),
            Input(value=str(cfg.ai.temperature), id="inp-temperature"),
            Static(""),
            Static("[bold]Интерфейс[/bold]"),
            Select(theme_opts, value=cfg.ui.theme, id="sel-theme"),
            Checkbox("Показывать вызовы инструментов", value=cfg.ui.show_tool_calls, id="cb-tools"),
            Checkbox("Показывать временные метки", value=cfg.ui.show_timestamps, id="cb-timestamps"),
            Static(""),
            Static("[bold]Безопасность[/bold]"),
            Checkbox("Подтверждение перед удалением", value=cfg.safety.confirm_destructive, id="cb-confirm-del"),
            Checkbox("Подтверждение перед sudo", value=cfg.safety.confirm_sudo, id="cb-confirm-sudo"),
            Static(""),
            Horizontal(
                Button("Сохранить", id="btn-save", variant="primary"),
                Button("Отмена", id="btn-cancel"),
                id="settings-buttons",
            ),
            id="settings-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-save":
            self._save()
            self.dismiss()

    def _save(self) -> None:
        cm = get_config_manager()
        cfg = cm.config

        try:
            sel_provider = self.query_one("#sel-provider", Select)
            if sel_provider.value:
                cfg.ai.provider = sel_provider.value

            cfg.ai.model = self.query_one("#inp-model", Input).value
            cfg.ai.base_url = self.query_one("#inp-baseurl", Input).value

            try:
                cfg.ai.temperature = float(self.query_one("#inp-temperature", Input).value)
            except ValueError:
                pass

            sel_theme = self.query_one("#sel-theme", Select)
            if sel_theme.value:
                cfg.ui.theme = sel_theme.value

            cfg.ui.show_tool_calls = self.query_one("#cb-tools", Checkbox).value
            cfg.ui.show_timestamps = self.query_one("#cb-timestamps", Checkbox).value
            cfg.safety.confirm_destructive = self.query_one("#cb-confirm-del", Checkbox).value
            cfg.safety.confirm_sudo = self.query_one("#cb-confirm-sudo", Checkbox).value

            cm.save()
        except Exception:
            pass

    CSS = """
    #settings-container {
        background: #16213e;
        border: round #0f3460;
        padding: 2 4;
        width: 70;
        height: auto;
        align: center middle;
    }
    Screen { align: center middle; background: #1a1a2e; }
    #settings-title { text-style: bold; color: #88c0d0; margin-bottom: 1; }
    Input { margin-bottom: 1; }
    Checkbox { margin-bottom: 1; }
    Select { margin-bottom: 1; }
    #settings-buttons { margin-top: 1; }
    #settings-buttons Button { margin-right: 1; }
    """
