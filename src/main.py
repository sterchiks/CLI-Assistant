"""Точка входа CLI Assistant."""

import asyncio
import logging
import os
import sys
from pathlib import Path

import click

# Настройка логирования до импорта остальных модулей
LOG_DIR = Path.home() / ".cli-assistant" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "error.log", encoding="utf-8"),
    ],
)

# Добавляем src в путь если запускаем напрямую
_src_dir = Path(__file__).parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


@click.command()
@click.option("--setup", is_flag=True, help="Запустить мастер настройки")
@click.option("--config", default=None, help="Путь к файлу конфигурации")
@click.option("--provider", default=None, help="AI провайдер (anthropic/gemini/openai_compatible)")
@click.option("--model", default=None, help="Название модели")
@click.option("--theme", default=None, help="Тема оформления")
@click.version_option(version="1.0.0", prog_name="CLI Assistant")
def main(
    setup: bool,
    config: str | None,
    provider: str | None,
    model: str | None,
    theme: str | None,
) -> None:
    """🤖 CLI Assistant — AI-ассистент для управления системой через терминал."""
    asyncio.run(_async_main(setup, config, provider, model, theme))


async def _async_main(
    setup: bool,
    config_path: str | None,
    provider: str | None,
    model: str | None,
    theme: str | None,
) -> None:
    """Асинхронная точка входа."""
    from src.settings.config_manager import get_config_manager

    # Инициализируем менеджер конфигурации
    cm = get_config_manager(config_path)

    # Применяем CLI-аргументы поверх конфига
    if provider:
        cm.config.ai.provider = provider
    if model:
        cm.config.ai.model = model
    if theme:
        cm.config.ui.theme = theme

    # Проверяем нужен ли Setup Wizard
    needs_setup = setup or not cm.is_configured()

    if needs_setup:
        from src.ui.setup_wizard import run_setup_wizard
        completed = await run_setup_wizard()
        if not completed:
            click.echo("Настройка отменена. Запустите снова для повторной настройки.")
            return
        # Перезагружаем конфиг после wizard
        cm.reload()

    # Запускаем главный UI
    from src.ui.chat_ui import CLIAssistantApp
    app = CLIAssistantApp()
    await app.run_async()


if __name__ == "__main__":
    main()
