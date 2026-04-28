"""Мастер первоначальной настройки CLI Assistant."""

import asyncio
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import (
    Button, Input, Label, RadioButton, RadioSet,
    Checkbox, Select, Static, Header, Footer
)
from textual.screen import Screen
from textual.binding import Binding

from ..settings.config_manager import get_config_manager
from ..ai.provider_factory import ProviderFactory
from .themes import get_theme, get_theme_names


class WelcomeScreen(Screen):
    """Шаг 1: Приветствие."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🤖 Добро пожаловать в CLI Assistant!", id="welcome-title"),
            Static(""),
            Static("Интерактивный AI-ассистент для управления системой"),
            Static("через естественный язык прямо в терминале."),
            Static(""),
            Static("Давайте настроим вашего ИИ-ассистента."),
            Static(""),
            Button("Начать настройку →", id="btn-start", variant="primary"),
            id="welcome-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            self.app.push_screen(ProviderScreen())

    CSS = """
    #welcome-container {
        align: center middle;
        width: 60;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #welcome-title {
        text-style: bold;
        color: #88c0d0;
        text-align: center;
    }
    Button {
        margin-top: 1;
        width: 100%;
    }
    """


class ProviderScreen(Screen):
    """Шаг 2: Выбор AI провайдера."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Шаг 2/6: Выбор AI провайдера", id="step-title"),
            Static(""),
            RadioSet(
                RadioButton("Anthropic (Claude) — рекомендуется", id="rb-anthropic", value=True),
                RadioButton("Google Gemini", id="rb-gemini"),
                RadioButton("OpenAI-совместимый (OpenAI, Groq, Ollama, и др.)", id="rb-openai"),
                id="provider-radio",
            ),
            Static(""),
            Horizontal(
                Button("← Назад", id="btn-back"),
                Button("Далее →", id="btn-next", variant="primary"),
                id="nav-buttons",
            ),
            id="provider-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-next":
            radio_set = self.query_one("#provider-radio", RadioSet)
            selected = radio_set.pressed_index
            providers = ["anthropic", "gemini", "openai_compatible"]
            self.app.wizard_data["provider"] = providers[selected]
            self.app.push_screen(ApiKeyScreen())

    CSS = """
    #provider-container {
        align: center middle;
        width: 70;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #step-title { text-style: bold; color: #88c0d0; }
    #nav-buttons { margin-top: 1; }
    #nav-buttons Button { margin-right: 1; }
    """


class ApiKeyScreen(Screen):
    """Шаг 3: Ввод API ключа."""

    def compose(self) -> ComposeResult:
        provider = self.app.wizard_data.get("provider", "anthropic")
        widgets = [
            Static("Шаг 3/6: Настройка API", id="step-title"),
            Static(""),
        ]

        if provider == "anthropic":
            widgets += [
                Label("Anthropic API Key:"),
                Input(placeholder="sk-ant-...", password=True, id="api-key-input"),
                Static("Получить ключ: https://console.anthropic.com", classes="hint"),
            ]
        elif provider == "gemini":
            widgets += [
                Label("Google Gemini API Key:"),
                Input(placeholder="AIza...", password=True, id="api-key-input"),
                Static("Получить ключ: https://aistudio.google.com", classes="hint"),
            ]
        else:
            widgets += [
                Label("Base URL:"),
                Select(
                    [
                        ("OpenAI — https://api.openai.com/v1", "https://api.openai.com/v1"),
                        ("Groq — https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1"),
                        ("Ollama (local) — http://localhost:11434/v1", "http://localhost:11434/v1"),
                        ("LM Studio — http://localhost:1234/v1", "http://localhost:1234/v1"),
                        ("OpenRouter — https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
                        ("Кастомный URL...", "custom"),
                    ],
                    id="base-url-select",
                ),
                Input(placeholder="https://...", id="base-url-custom", classes="hidden"),
                Label("API Key:"),
                Input(placeholder="API ключ (или 'ollama' для Ollama)", password=True, id="api-key-input"),
                Label("Название модели:"),
                Input(placeholder="gpt-4o, llama3, mistral...", id="model-input"),
            ]

        widgets += [
            Static(""),
            Static("", id="test-result"),
            Horizontal(
                Button("← Назад", id="btn-back"),
                Button("Проверить ключ", id="btn-test"),
                Button("Далее →", id="btn-next", variant="primary"),
                id="nav-buttons",
            ),
        ]

        yield Container(*widgets, id="apikey-container")

    def on_mount(self) -> None:
        try:
            self.query_one("#api-key-input", Input).focus()
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "base-url-select":
            custom_input = self.query_one("#base-url-custom", Input)
            if event.value == "custom":
                custom_input.remove_class("hidden")
            else:
                custom_input.add_class("hidden")
                self.app.wizard_data["base_url"] = event.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()

        elif event.button.id == "btn-test":
            await self._test_connection()

        elif event.button.id == "btn-next":
            self._save_data()
            self.app.push_screen(ModelScreen())

    def _save_data(self) -> None:
        try:
            api_key = self.query_one("#api-key-input", Input).value
            self.app.wizard_data["api_key"] = api_key

            provider = self.app.wizard_data.get("provider")
            if provider == "openai_compatible":
                select = self.query_one("#base-url-select", Select)
                if select.value == "custom":
                    base_url = self.query_one("#base-url-custom", Input).value
                else:
                    base_url = select.value
                self.app.wizard_data["base_url"] = base_url

                model_input = self.query_one("#model-input", Input)
                if model_input.value:
                    self.app.wizard_data["model"] = model_input.value
        except Exception:
            pass

    async def _test_connection(self) -> None:
        self._save_data()
        result_label = self.query_one("#test-result", Static)
        result_label.update("⏳ Проверяю подключение...")

        try:
            provider = ProviderFactory.create(
                provider_name=self.app.wizard_data.get("provider", "anthropic"),
                api_key=self.app.wizard_data.get("api_key", ""),
                model=self.app.wizard_data.get("model", ""),
                base_url=self.app.wizard_data.get("base_url", ""),
            )
            if provider:
                ok = await provider.test_connection()
                if ok:
                    result_label.update("✅ Подключение успешно!")
                else:
                    result_label.update("❌ Ошибка подключения. Проверьте ключ.")
            else:
                result_label.update("❌ Не удалось создать провайдер")
        except Exception as e:
            result_label.update(f"❌ Ошибка: {e}")

    CSS = """
    #apikey-container {
        align: center middle;
        width: 72;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #step-title { text-style: bold; color: #88c0d0; }
    .hint { color: #888888; }
    .hidden { display: none; }
    #nav-buttons { margin-top: 1; }
    #nav-buttons Button { margin-right: 1; }
    #test-result { color: #88c0d0; }
    Input { margin-bottom: 1; }
    """


class ModelScreen(Screen):
    """Шаг 4: Выбор модели."""

    def compose(self) -> ComposeResult:
        provider = self.app.wizard_data.get("provider", "anthropic")
        models = ProviderFactory.get_models_for_provider(provider)
        options = [(m, m) for m in models]
        if not options:
            options = [("(введите вручную)", "")]

        yield Container(
            Static("Шаг 4/6: Выбор модели", id="step-title"),
            Static(""),
            Label("Выберите модель:"),
            Select(options, id="model-select"),
            Static(""),
            Horizontal(
                Button("← Назад", id="btn-back"),
                Button("Далее →", id="btn-next", variant="primary"),
                id="nav-buttons",
            ),
            id="model-container",
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "model-select" and event.value:
            self.app.wizard_data["model"] = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-next":
            self.app.push_screen(SafetyScreen())

    CSS = """
    #model-container {
        align: center middle;
        width: 60;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #step-title { text-style: bold; color: #88c0d0; }
    #nav-buttons { margin-top: 1; }
    #nav-buttons Button { margin-right: 1; }
    """


class SafetyScreen(Screen):
    """Шаг 5: Настройки безопасности."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Шаг 5/6: Настройки безопасности", id="step-title"),
            Static(""),
            Checkbox("Спрашивать подтверждение перед удалением файлов", value=True, id="cb-confirm-delete"),
            Checkbox("Спрашивать подтверждение перед sudo-командами", value=True, id="cb-confirm-sudo"),
            Checkbox("Показывать вызовы инструментов в чате", value=True, id="cb-show-tools"),
            Static(""),
            Horizontal(
                Button("← Назад", id="btn-back"),
                Button("Далее →", id="btn-next", variant="primary"),
                id="nav-buttons",
            ),
            id="safety-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-next":
            self.app.wizard_data["confirm_destructive"] = self.query_one("#cb-confirm-delete", Checkbox).value
            self.app.wizard_data["confirm_sudo"] = self.query_one("#cb-confirm-sudo", Checkbox).value
            self.app.wizard_data["show_tool_calls"] = self.query_one("#cb-show-tools", Checkbox).value
            self.app.push_screen(ThemeScreen())

    CSS = """
    #safety-container {
        align: center middle;
        width: 65;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #step-title { text-style: bold; color: #88c0d0; }
    Checkbox { margin-bottom: 1; }
    #nav-buttons { margin-top: 1; }
    #nav-buttons Button { margin-right: 1; }
    """


class ThemeScreen(Screen):
    """Шаг 6: Выбор темы."""

    def compose(self) -> ComposeResult:
        theme_options = [(t.capitalize(), t) for t in get_theme_names()]
        yield Container(
            Static("Шаг 6/6: Выбор темы", id="step-title"),
            Static(""),
            Label("Тема оформления:"),
            Select(theme_options, id="theme-select"),
            Static(""),
            Static("Тема применится после перезапуска", classes="hint"),
            Static(""),
            Horizontal(
                Button("← Назад", id="btn-back"),
                Button("Завершить настройку ✓", id="btn-finish", variant="primary"),
                id="nav-buttons",
            ),
            id="theme-container",
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "theme-select":
            self.app.wizard_data["theme"] = event.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-finish":
            await self._save_config()
            self.app.push_screen(DoneScreen())

    async def _save_config(self) -> None:
        """Сохраняет конфигурацию из wizard_data."""
        data = self.app.wizard_data
        cm = get_config_manager()
        config = cm.config

        config.ai.provider = data.get("provider", "anthropic")
        config.ai.model = data.get("model", "")
        config.ai.base_url = data.get("base_url", "")
        config.safety.confirm_destructive = data.get("confirm_destructive", True)
        config.safety.confirm_sudo = data.get("confirm_sudo", True)
        config.ui.show_tool_calls = data.get("show_tool_calls", True)
        config.ui.theme = data.get("theme", "dark")

        cm.save()
        api_key = data.get("api_key", "")
        if api_key:
            cm.set_api_key(api_key)

    CSS = """
    #theme-container {
        align: center middle;
        width: 60;
        height: auto;
        border: round #0f3460;
        padding: 2 4;
        background: #16213e;
    }
    #step-title { text-style: bold; color: #88c0d0; }
    .hint { color: #888888; }
    #nav-buttons { margin-top: 1; }
    #nav-buttons Button { margin-right: 1; }
    """


class DoneScreen(Screen):
    """Финальный экран — настройка завершена."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("✅ Настройка завершена!", id="done-title"),
            Static(""),
            Static("CLI Assistant готов к работе."),
            Static(""),
            Static("Полезные команды:"),
            Static("  /help     — список всех команд"),
            Static("  /settings — изменить настройки"),
            Static("  /theme    — сменить тему"),
            Static(""),
            Button("Начать работу 🚀", id="btn-start", variant="primary"),
            id="done-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            self.app.exit(result=True)

    CSS = """
    #done-container {
        align: center middle;
        width: 50;
        height: auto;
        border: round #0f7a3a;
        padding: 2 4;
        background: #16213e;
    }
    #done-title { text-style: bold; color: #4caf50; text-align: center; }
    Button { margin-top: 1; width: 100%; }
    """


class SetupWizardApp(App):
    """Приложение мастера настройки."""

    CSS = """
    Screen {
        background: #1a1a2e;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Выход"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.wizard_data: dict = {}

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())


async def run_setup_wizard() -> bool:
    """Запускает мастер настройки. Возвращает True если настройка завершена."""
    app = SetupWizardApp()
    result = await app.run_async()
    return bool(result)
