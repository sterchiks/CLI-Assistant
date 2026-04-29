"""Точка входа CLI Assistant.

Здесь же сосредоточена вся настройка логирования:

* `~/.cli-assistant/logs/app.log`            — обычный лог (INFO+) с ротацией
* `~/.cli-assistant/logs/error.log`          — только ошибки (ERROR+)
* `~/.cli-assistant/logs/crashes/<ts>.log`   — отдельный файл на каждый
   необработанный crash с полным traceback и системной информацией.

Перехватываются три источника исключений:
  1) синхронные (`sys.excepthook`),
  2) исключения в потоках (`threading.excepthook`, py3.8+),
  3) необработанные исключения в asyncio loop'ах
     (через `loop.set_exception_handler`).
"""

import asyncio
import logging
import os
import platform
import sys
import threading
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import click

# ─── Каталоги логов ───────────────────────────────────────────────────────────

LOG_DIR = Path.home() / ".cli-assistant" / "logs"
CRASH_DIR = LOG_DIR / "crashes"


def _ensure_log_dirs() -> None:
    """Создаёт директории логов; ошибки тихо игнорируем — fallback в stderr."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        CRASH_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _build_app_handler() -> logging.Handler:
    """Файловый handler для обычных логов (INFO+) с rotation."""
    try:
        _ensure_log_dirs()
        return RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=2_097_152,   # 2 МБ
            backupCount=5,
            encoding="utf-8",
        )
    except OSError:
        return logging.StreamHandler(sys.stderr)


def _build_error_handler() -> logging.Handler:
    """Файловый handler только для ERROR+ с rotation."""
    try:
        _ensure_log_dirs()
        h = RotatingFileHandler(
            LOG_DIR / "error.log",
            maxBytes=1_048_576,
            backupCount=3,
            encoding="utf-8",
        )
        h.setLevel(logging.ERROR)
        return h
    except OSError:
        return logging.StreamHandler(sys.stderr)


# Конфигурируем root-логгер ДО импорта остальных модулей.
_app_handler = _build_app_handler()
_app_handler.setLevel(logging.INFO)
_err_handler = _build_error_handler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_app_handler, _err_handler],
)

# Заглушаем шумные сторонние логгеры (httpx стримит каждый chunk).
for noisy in ("httpx", "httpcore", "anthropic", "openai", "google", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("cli-assistant.main")
logger.info("=" * 60)
logger.info(
    "Запуск CLI Assistant pid=%s python=%s os=%s",
    os.getpid(), sys.version.split()[0], platform.platform(),
)


# ─── Crash logger ─────────────────────────────────────────────────────────────

def _system_snapshot() -> str:
    """Краткий снимок окружения для crash-отчёта."""
    try:
        return (
            f"timestamp:   {datetime.now().isoformat(timespec='seconds')}\n"
            f"pid:         {os.getpid()}\n"
            f"python:      {sys.version}\n"
            f"executable:  {sys.executable}\n"
            f"platform:    {platform.platform()}\n"
            f"cwd:         {os.getcwd()}\n"
            f"argv:        {sys.argv}\n"
        )
    except Exception:
        return "(не удалось собрать снимок окружения)\n"


def _write_crash(
    exc_type, exc_value, exc_tb, *, source: str = "sync", extra: str = ""
) -> Path | None:
    """Сохраняет полный crash-отчёт в отдельный файл и возвращает его путь."""
    try:
        _ensure_log_dirs()
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = CRASH_DIR / f"crash-{ts}.log"
        with path.open("w", encoding="utf-8") as f:
            f.write(f"=== CLI Assistant CRASH REPORT ({source}) ===\n")
            f.write(_system_snapshot())
            if extra:
                f.write("\n--- extra ---\n")
                f.write(extra.rstrip() + "\n")
            f.write("\n--- traceback ---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        logger.error("Crash сохранён: %s (%s: %s)", path, exc_type.__name__, exc_value)
        # Дублируем в stderr — чтобы пользователь увидел путь даже при крахе UI.
        try:
            sys.stderr.write(
                f"\n💥 CLI Assistant упал. Подробный отчёт: {path}\n"
            )
        except Exception:
            pass
        return path
    except Exception:
        # Совсем последний шанс — печатаем в stderr.
        try:
            sys.stderr.write("\n💥 Crash без возможности записать файл лога:\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
        except Exception:
            pass
        return None


def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:  # pragma: no cover
    # KeyboardInterrupt — это нормальный выход, не пишем как crash.
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _write_crash(exc_type, exc_value, exc_tb, source="sync")


def _thread_excepthook(args) -> None:  # pragma: no cover
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    _write_crash(
        args.exc_type, args.exc_value, args.exc_traceback,
        source=f"thread:{getattr(args.thread, 'name', '?')}",
    )


def _asyncio_exception_handler(loop, context) -> None:  # pragma: no cover
    exc = context.get("exception")
    msg = context.get("message", "")
    if exc is None:
        # Нет реального исключения, но asyncio считает это ошибкой
        # (например, «Task was destroyed but it is pending!»). Логируем как warning.
        logger.warning("asyncio: %s | context=%r", msg, context)
        return
    _write_crash(
        type(exc), exc, exc.__traceback__,
        source="asyncio",
        extra=f"message: {msg}\ncontext keys: {list(context.keys())}",
    )


sys.excepthook = _sys_excepthook
try:
    threading.excepthook = _thread_excepthook  # py3.8+
except Exception:  # pragma: no cover
    pass


# ─── Путь src ─────────────────────────────────────────────────────────────────

_src_dir = Path(__file__).parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


# ─── CLI ──────────────────────────────────────────────────────────────────────

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
    try:
        asyncio.run(_async_main(setup, config, provider, model, theme))
    except KeyboardInterrupt:
        logger.info("Интерактивный выход по Ctrl+C")
    except Exception:
        # Пробрасываем дальше — попадёт в sys.excepthook и будет crash-файл.
        raise
    finally:
        logger.info("CLI Assistant завершён")


async def _async_main(
    setup: bool,
    config_path: str | None,
    provider: str | None,
    model: str | None,
    theme: str | None,
) -> None:
    """Асинхронная точка входа."""
    # Регистрируем обработчик исключений на текущий event loop.
    try:
        asyncio.get_event_loop().set_exception_handler(_asyncio_exception_handler)
    except Exception:  # pragma: no cover
        pass

    from src.settings import config_manager as config_module

    if config_path:
        config_module.CONFIG_FILE = Path(config_path).expanduser().resolve()
        config_module.CONFIG_DIR = config_module.CONFIG_FILE.parent

    # Инициализируем менеджер конфигурации
    cm = config_module.get_config_manager()
    logger.info(
        "Конфиг загружен: provider=%s model=%s theme=%s",
        cm.config.ai.provider, cm.config.ai.model, cm.config.ui.theme,
    )

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
        cm.load()

    # Запускаем главный UI
    from src.ui.chat_ui import CLIAssistantApp
    app = CLIAssistantApp()
    logger.info("UI стартует")
    await app.run_async()


if __name__ == "__main__":
    main()
