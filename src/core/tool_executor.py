"""Выполнение инструментов ИИ с проверками безопасности."""

import json
import logging
import time
from typing import Any, Callable, Awaitable, Optional

from ..tools.file_reader import FileReader
from ..tools.file_manager import FileManager
from ..tools.file_editor import FileEditor
from ..tools.terminal_manager import TerminalManager
from ..tools.disk_manager import DiskManager
from ..tools.sudo_manager import SudoManager
from ..tools.network_tool import NetworkTool
from ..tools.package_manager import PackageManager
from ..tools.process_manager import ProcessManager
from ..tools.archive_tool import ArchiveTool
from ..tools.git_tool import GitTool
from ..tools.service_manager import ServiceManager
from ..tools.app_manager import AppManager
from ..tools.cron_tool import CronTool
from .safety import SafetyChecker, SafetyError, CATASTROPHIC_REFUSAL


# Имена tool-инструментов, у которых поле `command` (или подобное) может
# содержать произвольную shell-команду от модели. Такие команды мы
# обязаны проверять на катастрофичность ДО любых других действий —
# даже если модель её сама уже «согласовала».
_SHELL_COMMAND_TOOLS: dict[str, tuple[str, ...]] = {
    "run_command": ("command",),
    "run_command_sudo": ("command",),
    "run_in_new_terminal": ("command",),
    "open_terminal": ("command",),
    "run_as_root": ("command",),
    "add_cron": ("command",),
    "edit_cron": ("command",),
}


logger = logging.getLogger(__name__)

# Описания инструментов для function calling API
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Читает содержимое текстового файла",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "encoding": {"type": "string", "description": "Кодировка (по умолчанию utf-8)", "default": "utf-8"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file_lines",
        "description": "Читает диапазон строк файла",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start": {"type": "integer", "description": "Начальная строка (1-based)"},
                "end": {"type": "integer", "description": "Конечная строка (включительно)"},
            },
            "required": ["path", "start", "end"],
        },
    },
    {
        "name": "get_file_info",
        "description": "Возвращает метаданные файла: размер, права, владелец, дата изменения",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "Список файлов и папок в директории",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "show_hidden": {"type": "boolean", "default": False},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_in_file",
        "description": "Поиск текста или regex в файле",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string"},
                "regex": {"type": "boolean", "default": False},
            },
            "required": ["path", "pattern"],
        },
    },
    {
        "name": "search_files",
        "description": "Поиск файлов по имени/паттерну в директории",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string"},
                "pattern": {"type": "string"},
                "file_type": {"type": "string", "enum": ["file", "dir"], "description": "Тип: file или dir"},
            },
            "required": ["directory", "pattern"],
        },
    },
    {
        "name": "copy_file",
        "description": "Копирует файл",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "move_file",
        "description": "Перемещает файл",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "delete_file",
        "description": "Удаляет файл (ДЕСТРУКТИВНАЯ ОПЕРАЦИЯ)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "secure": {"type": "boolean", "default": False, "description": "Безопасное затирание"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_directory",
        "description": "Создаёт директорию",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "parents": {"type": "boolean", "default": True},
            },
            "required": ["path"],
        },
    },
    {
        "name": "delete_directory",
        "description": "Удаляет директорию (ДЕСТРУКТИВНАЯ ОПЕРАЦИЯ)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    },
    {
        "name": "rename",
        "description": "Переименовывает файл или директорию",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "new_name": {"type": "string"},
            },
            "required": ["path", "new_name"],
        },
    },
    {
        "name": "set_permissions",
        "description": "Устанавливает права доступа (chmod)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "mode": {"type": "string", "description": "Права: '755' или 'rwxr-xr-x'"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path", "mode"],
        },
    },
    {
        "name": "get_disk_usage",
        "description": "Показывает использование диска для пути",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Полностью перезаписывает файл новым содержимым",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_to_file",
        "description": "Добавляет текст в конец файла",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "replace_in_file",
        "description": "Заменяет текст в файле",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "all_occurrences": {"type": "boolean", "default": True},
            },
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "create_file",
        "description": "Создаёт новый файл с опциональным шаблоном",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "default": ""},
                "template": {"type": "string", "description": "Шаблон: python_script, bash_script, json, yaml, markdown, html, dockerfile"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_backup",
        "description": "Создаёт резервную копию файла (.bak)",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Выполняет команду в терминале и возвращает результат",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "description": "Рабочая директория"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_running_processes",
        "description": "Список запущенных процессов",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "kill_process",
        "description": "Завершает процесс по PID",
        "input_schema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer"},
                "signal": {"type": "string", "default": "TERM", "enum": ["TERM", "KILL"]},
            },
            "required": ["pid"],
        },
    },
    {
        "name": "get_system_info",
        "description": "Системная информация: CPU, RAM, диск, OS, uptime",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_partitions",
        "description": "Список разделов диска с размерами",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_block_devices",
        "description": "Список блочных устройств (аналог lsblk)",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_as_root",
        "description": "Выполняет команду с правами root (sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    # --- Network ---
    {
        "name": "ping",
        "description": "Пинг хоста (отдельный subprocess)",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "count": {"type": "integer", "default": 4},
            },
            "required": ["host"],
        },
    },
    {
        "name": "check_port",
        "description": "Проверить TCP-порт удалённого хоста",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "timeout": {"type": "number", "default": 3},
            },
            "required": ["host", "port"],
        },
    },
    {
        "name": "list_open_ports",
        "description": "Список открытых TCP-портов на этой машине",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_network_interfaces",
        "description": "Сетевые интерфейсы и их адреса",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "download_file",
        "description": "Скачивает файл по URL",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["url", "destination"],
        },
    },
    {
        "name": "http_request",
        "description": "HTTP-запрос (GET/POST/PUT/DELETE) с возвратом статуса и тела",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "default": "GET"},
                "headers": {"type": "object"},
                "data": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_public_ip",
        "description": "Внешний (публичный) IP-адрес",
        "input_schema": {"type": "object", "properties": {}},
    },
    # --- PackageManager ---
    {
        "name": "install_package",
        "description": "Установить пакет (apt/dnf/pacman). Системные требуют sudo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "manager": {"type": "string", "default": "auto"},
            },
            "required": ["package"],
        },
    },
    {
        "name": "remove_package",
        "description": "Удалить пакет (apt/dnf/pacman)",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "manager": {"type": "string", "default": "auto"},
            },
            "required": ["package"],
        },
    },
    {
        "name": "update_packages",
        "description": "Обновить все пакеты системы",
        "input_schema": {
            "type": "object",
            "properties": {"manager": {"type": "string", "default": "auto"}},
        },
    },
    {
        "name": "search_package",
        "description": "Поиск пакетов в репозиториях",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "manager": {"type": "string", "default": "auto"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_installed_packages",
        "description": "Список установленных пакетов",
        "input_schema": {
            "type": "object",
            "properties": {"manager": {"type": "string", "default": "auto"}},
        },
    },
    {
        "name": "pip_install",
        "description": "Установить Python-пакет (pip --user по умолчанию)",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "user": {"type": "boolean", "default": True},
            },
            "required": ["package"],
        },
    },
    {
        "name": "npm_install",
        "description": "Установить npm-пакет",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "global_": {"type": "boolean", "default": False},
                "cwd": {"type": "string", "default": ""},
            },
            "required": ["package"],
        },
    },
    # --- ProcessManager (psutil) ---
    {
        "name": "list_processes",
        "description": "Список процессов с сортировкой (cpu/memory/name/pid)",
        "input_schema": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "default": "cpu"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "find_process",
        "description": "Поиск процессов по имени/cmdline",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_process_info",
        "description": "Детальная информация о процессе по PID",
        "input_schema": {
            "type": "object",
            "properties": {"pid": {"type": "integer"}},
            "required": ["pid"],
        },
    },
    {
        "name": "get_top_processes",
        "description": "Топ N процессов по потреблению памяти",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
        },
    },
    {
        "name": "kill_process_advanced",
        "description": "Завершить процесс по PID (force=True для SIGKILL)",
        "input_schema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["pid"],
        },
    },
    # --- ArchiveTool ---
    {
        "name": "create_archive",
        "description": "Создать архив (zip/tar/tar.gz/tar.bz2/tar.xz)",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "format": {"type": "string", "default": "tar.gz"},
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "extract_archive",
        "description": "Распаковать архив (zip/tar/*) в директорию",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "list_archive",
        "description": "Список файлов в архиве",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "get_archive_size",
        "description": "Размер архива и суммарный размер после распаковки",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    # --- GitTool ---
    {
        "name": "git_status",
        "description": "git status (короткий вывод)",
        "input_schema": {
            "type": "object",
            "properties": {"cwd": {"type": "string", "default": "."}},
        },
    },
    {
        "name": "git_log",
        "description": "История коммитов",
        "input_schema": {
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": "."},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "git_commit",
        "description": "git add -A + git commit -m",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "add_all": {"type": "boolean", "default": True},
                "cwd": {"type": "string", "default": "."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_push",
        "description": "git push",
        "input_schema": {
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin"},
                "branch": {"type": "string", "default": ""},
                "cwd": {"type": "string", "default": "."},
            },
        },
    },
    {
        "name": "git_pull",
        "description": "git pull",
        "input_schema": {
            "type": "object",
            "properties": {
                "remote": {"type": "string", "default": "origin"},
                "cwd": {"type": "string", "default": "."},
            },
        },
    },
    {
        "name": "git_clone",
        "description": "git clone",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "destination": {"type": "string", "default": ""},
            },
            "required": ["url"],
        },
    },
    {
        "name": "git_branch",
        "description": "Список веток + текущая ветка",
        "input_schema": {
            "type": "object",
            "properties": {"cwd": {"type": "string", "default": "."}},
        },
    },
    {
        "name": "git_checkout",
        "description": "git checkout (create=True для -b)",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string"},
                "create": {"type": "boolean", "default": False},
                "cwd": {"type": "string", "default": "."},
            },
            "required": ["branch"],
        },
    },
    {
        "name": "git_diff",
        "description": "git diff (несохранённые изменения)",
        "input_schema": {
            "type": "object",
            "properties": {"cwd": {"type": "string", "default": "."}},
        },
    },
    # --- ServiceManager ---
    {
        "name": "list_services",
        "description": "Список systemd-сервисов (filter: all/running/failed/inactive)",
        "input_schema": {
            "type": "object",
            "properties": {"status_filter": {"type": "string", "default": "all"}},
        },
    },
    {
        "name": "service_status",
        "description": "Статус systemd-сервиса",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "start_service",
        "description": "Запустить systemd-сервис (требует sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "stop_service",
        "description": "Остановить systemd-сервис (требует sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "restart_service",
        "description": "Перезапустить systemd-сервис (требует sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "enable_service",
        "description": "Включить автозапуск сервиса (требует sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "disable_service",
        "description": "Отключить автозапуск сервиса (требует sudo)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_service_logs",
        "description": "Логи systemd-сервиса через journalctl",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "lines": {"type": "integer", "default": 50},
            },
            "required": ["name"],
        },
    },
    # --- AppManager ---
    {
        "name": "open_application",
        "description": "Открыть GUI-приложение, опционально на указанном рабочем столе",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "workspace": {"type": "integer", "default": 1},
                "args": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "close_application",
        "description": "Закрыть приложение по имени или PID",
        "input_schema": {
            "type": "object",
            "properties": {"identifier": {"type": "string"}},
            "required": ["identifier"],
        },
    },
    {
        "name": "switch_workspace",
        "description": "Переключиться на рабочий стол (1-based)",
        "input_schema": {
            "type": "object",
            "properties": {"workspace": {"type": "integer"}},
            "required": ["workspace"],
        },
    },
    {
        "name": "move_window_to_workspace",
        "description": "Переместить окно (по подстроке заголовка) на другой рабочий стол",
        "input_schema": {
            "type": "object",
            "properties": {
                "window_title": {"type": "string"},
                "workspace": {"type": "integer"},
            },
            "required": ["window_title", "workspace"],
        },
    },
    {
        "name": "list_open_applications",
        "description": "Список открытых GUI-окон с PID/title/workspace",
        "input_schema": {"type": "object", "properties": {}},
    },
    # --- CronTool ---
    {
        "name": "list_crons",
        "description": "Список cron-заданий текущего пользователя",
        "input_schema": {
            "type": "object",
            "properties": {"user": {"type": "string", "default": "current"}},
        },
    },
    {
        "name": "add_cron",
        "description": "Добавить cron-задание. schedule поддерживает '* * * * *' и человеческий вид: 'every 5 minutes', 'daily', 'every day at 9:30'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schedule": {"type": "string"},
                "command": {"type": "string"},
                "comment": {"type": "string", "default": ""},
            },
            "required": ["schedule", "command"],
        },
    },
    {
        "name": "remove_cron",
        "description": "Удалить cron-задание по индексу (из list_crons)",
        "input_schema": {
            "type": "object",
            "properties": {"index": {"type": "integer"}},
            "required": ["index"],
        },
    },
    {
        "name": "edit_cron",
        "description": "Изменить расписание/команду существующего cron-задания",
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
                "schedule": {"type": "string", "default": ""},
                "command": {"type": "string", "default": ""},
            },
            "required": ["index"],
        },
    },
]

# Деструктивные инструменты требующие подтверждения
DESTRUCTIVE_TOOLS = {"delete_file", "delete_directory", "write_file"}
SUDO_TOOLS = {"run_as_root", "mount_partition", "unmount_partition"}


def get_tool_definitions_for_provider(provider: str) -> list[dict]:
    """Конвертирует определения инструментов в формат конкретного провайдера."""
    if provider == "anthropic":
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in TOOL_DEFINITIONS
        ]
    elif provider in ("openai_compatible", "gemini"):
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in TOOL_DEFINITIONS
        ]
    return TOOL_DEFINITIONS


class ToolExecutor:
    """Выполняет инструменты ИИ с проверками безопасности."""

    def __init__(self, safety: SafetyChecker, sudo_manager: SudoManager) -> None:
        self._safety = safety
        self._sudo = sudo_manager
        self._file_reader = FileReader()
        self._file_manager = FileManager()
        self._file_editor = FileEditor()
        self._terminal = TerminalManager()
        self._disk = DiskManager()
        self._network = NetworkTool()
        self._packages = PackageManager()
        self._processes = ProcessManager()
        self._archives = ArchiveTool()
        self._git = GitTool()
        self._services = ServiceManager()
        self._apps = AppManager()
        self._cron = CronTool()
        # Callback для уведомления UI о выполнении инструмента
        self._on_tool_start: Optional[Callable[[str, dict], None]] = None
        self._on_tool_done: Optional[Callable[[str, Any, float], None]] = None

    def set_callbacks(
        self,
        on_start: Optional[Callable[[str, dict], None]] = None,
        on_done: Optional[Callable[[str, Any, float], None]] = None,
    ) -> None:
        """Устанавливает callbacks для уведомления UI."""
        self._on_tool_start = on_start
        self._on_tool_done = on_done

    async def execute(self, tool_name: str, tool_input: dict) -> Any:
        """
        Выполняет инструмент по имени.
        Возвращает результат или строку с ошибкой.
        """
        start_time = time.time()

        if self._on_tool_start:
            self._on_tool_start(tool_name, tool_input)

        try:
            result = await self._dispatch(tool_name, tool_input)
        except SafetyError as e:
            result = {"error": str(e)}
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            result = {"error": f"Ошибка выполнения {tool_name}: {e}"}

        elapsed = time.time() - start_time
        if self._on_tool_done:
            self._on_tool_done(tool_name, result, elapsed)

        return result

    async def _dispatch(self, tool_name: str, inp: dict) -> Any:
        """Диспетчер инструментов."""

        # ─── ЖЁСТКИЙ ХАРД-БЛОК КАТАСТРОФИЧЕСКИХ КОМАНД ─────────────────────
        # Если tool принимает shell-команду (run_command, run_as_root,
        # run_in_new_terminal, add_cron и т.п.) — проверяем её ДО любых
        # подтверждений. Подтвердить такое нельзя в принципе. Возвращаем
        # фразу-отказ, которая попадает обратно к модели как результат
        # tool-вызова — модель увидит её и (по системному промпту) повторит
        # пользователю как свой ответ.
        if tool_name in _SHELL_COMMAND_TOOLS:
            for field in _SHELL_COMMAND_TOOLS[tool_name]:
                cmd = inp.get(field) or ""
                if not isinstance(cmd, str):
                    continue
                hit = self._safety.check_catastrophic_command(cmd)
                if hit:
                    logger.warning(
                        "Хард-блок катастрофической команды в %s: %r (%s)",
                        tool_name, cmd, hit,
                    )
                    return {
                        "blocked": True,
                        "refusal": CATASTROPHIC_REFUSAL,
                        "reason": (
                            f"Команда заблокирована на уровне системы безопасности: {hit}. "
                            f"Эта команда уничтожает систему/диск/домашнюю папку и не может "
                            f"быть выполнена ни при каких условиях. Сообщи пользователю буквально: "
                            f"«{CATASTROPHIC_REFUSAL}»."
                        ),
                    }

        # --- FileReader ---
        if tool_name == "read_file":
            self._safety.check_path(inp["path"])

            self._safety.check_file_size(inp["path"])
            return self._file_reader.read_file(inp["path"], inp.get("encoding", "utf-8"))

        elif tool_name == "read_file_lines":
            self._safety.check_path(inp["path"])
            return self._file_reader.read_file_lines(inp["path"], inp["start"], inp["end"])

        elif tool_name == "get_file_info":
            self._safety.check_path(inp["path"])
            return self._file_reader.get_file_info(inp["path"])

        elif tool_name == "list_directory":
            self._safety.check_path(inp["path"])
            return self._file_reader.list_directory(
                inp["path"],
                inp.get("show_hidden", False),
                inp.get("recursive", False),
            )

        elif tool_name == "search_in_file":
            self._safety.check_path(inp["path"])
            return self._file_reader.search_in_file(inp["path"], inp["pattern"], inp.get("regex", False))

        elif tool_name == "search_files":
            self._safety.check_path(inp["directory"])
            return self._file_reader.search_files(inp["directory"], inp["pattern"], inp.get("file_type"))

        # --- FileManager ---
        elif tool_name == "copy_file":
            self._safety.check_path(inp["src"])
            return self._file_manager.copy_file(inp["src"], inp["dst"], inp.get("overwrite", False))

        elif tool_name == "move_file":
            self._safety.check_path(inp["src"])
            confirmed = await self._safety.confirm_destructive(
                "Перемещение файла", f"{inp['src']} → {inp['dst']}"
            )
            if not confirmed:
                return {"cancelled": True}
            return self._file_manager.move_file(inp["src"], inp["dst"])

        elif tool_name == "delete_file":
            self._safety.check_path(inp["path"])
            confirmed = await self._safety.confirm_destructive(
                "Удаление файла", inp["path"]
            )
            if not confirmed:
                return {"cancelled": True}
            return self._file_manager.delete_file(inp["path"], inp.get("secure", False))

        elif tool_name == "create_directory":
            return self._file_manager.create_directory(inp["path"], inp.get("parents", True))

        elif tool_name == "delete_directory":
            self._safety.check_path(inp["path"])
            if inp.get("recursive", False):
                confirmed = await self._safety.confirm_destructive(
                    "Рекурсивное удаление директории", inp["path"]
                )
                if not confirmed:
                    return {"cancelled": True}
            return self._file_manager.delete_directory(inp["path"], inp.get("recursive", False))

        elif tool_name == "rename":
            self._safety.check_path(inp["path"])
            return self._file_manager.rename(inp["path"], inp["new_name"])

        elif tool_name == "set_permissions":
            self._safety.check_path(inp["path"])
            return self._file_manager.set_permissions(inp["path"], inp["mode"], inp.get("recursive", False))

        elif tool_name == "get_disk_usage":
            return self._file_manager.get_disk_usage(inp["path"])

        # --- FileEditor ---
        elif tool_name == "write_file":
            self._safety.check_path(inp["path"])
            confirmed = await self._safety.confirm_destructive(
                "Перезапись файла", inp["path"]
            )
            if not confirmed:
                return {"cancelled": True}
            return self._file_editor.write_file(inp["path"], inp["content"], inp.get("encoding", "utf-8"))

        elif tool_name == "append_to_file":
            self._safety.check_path(inp["path"])
            return self._file_editor.append_to_file(inp["path"], inp["content"])

        elif tool_name == "replace_in_file":
            self._safety.check_path(inp["path"])
            return self._file_editor.replace_in_file(
                inp["path"], inp["old"], inp["new"], inp.get("all_occurrences", True)
            )

        elif tool_name == "create_file":
            return self._file_editor.create_file(
                inp["path"], inp.get("content", ""), inp.get("template")
            )

        elif tool_name == "create_backup":
            self._safety.check_path(inp["path"])
            return self._file_editor.create_backup(inp["path"])

        # --- TerminalManager ---
        elif tool_name == "run_command":
            warning = self._safety.check_dangerous_command(inp["command"])
            if warning:
                confirmed = await self._safety.confirm_destructive(warning, inp["command"])
                if not confirmed:
                    return {"cancelled": True}
            return await self._terminal.run_command(
                inp["command"],
                inp.get("cwd"),
                inp.get("timeout", 60),
            )

        elif tool_name == "get_running_processes":
            return self._terminal.get_running_processes()

        elif tool_name == "kill_process":
            confirmed = await self._safety.confirm_destructive(
                "Завершение процесса", f"PID: {inp['pid']}"
            )
            if not confirmed:
                return {"cancelled": True}
            return self._terminal.kill_process(inp["pid"], inp.get("signal", "TERM"))

        elif tool_name == "get_system_info":
            return self._terminal.get_system_info()

        # --- DiskManager ---
        elif tool_name == "list_partitions":
            return self._disk.list_partitions()

        elif tool_name == "list_block_devices":
            return self._disk.list_block_devices()

        # --- SudoManager ---
        elif tool_name == "run_as_root":
            confirmed = await self._safety.confirm_sudo(inp["command"])
            if not confirmed:
                return {"cancelled": True}
            warning = self._safety.check_dangerous_command(inp["command"])
            if warning:
                confirmed2 = await self._safety.confirm_destructive(warning, inp["command"])
                if not confirmed2:
                    return {"cancelled": True}
            return await self._sudo.run_as_root(inp["command"])

        # --- NetworkTool ---
        elif tool_name == "ping":
            return await self._network.ping(inp["host"], inp.get("count", 4))
        elif tool_name == "check_port":
            return await self._network.check_port(
                inp["host"], inp["port"], inp.get("timeout", 3)
            )
        elif tool_name == "list_open_ports":
            return self._network.list_open_ports()
        elif tool_name == "get_network_interfaces":
            return self._network.get_network_interfaces()
        elif tool_name == "download_file":
            self._safety.check_path(inp["destination"])
            return await self._network.download_file(inp["url"], inp["destination"])
        elif tool_name == "http_request":
            return await self._network.http_request(
                inp["url"],
                inp.get("method", "GET"),
                inp.get("headers"),
                inp.get("data"),
            )
        elif tool_name == "get_public_ip":
            return await self._network.get_public_ip()

        # --- PackageManager ---
        elif tool_name == "install_package":
            confirmed = await self._safety.confirm_destructive(
                "Установка пакета", inp["package"]
            )
            if not confirmed:
                return {"cancelled": True}
            return await self._packages.install(inp["package"], inp.get("manager", "auto"), self._sudo)
        elif tool_name == "remove_package":
            confirmed = await self._safety.confirm_destructive(
                "Удаление пакета", inp["package"]
            )
            if not confirmed:
                return {"cancelled": True}
            return await self._packages.remove(inp["package"], inp.get("manager", "auto"), self._sudo)
        elif tool_name == "update_packages":
            confirmed = await self._safety.confirm_destructive(
                "Обновление всех пакетов системы", "update_packages"
            )
            if not confirmed:
                return {"cancelled": True}
            return await self._packages.update(inp.get("manager", "auto"), self._sudo)
        elif tool_name == "search_package":
            return await self._packages.search(inp["query"], inp.get("manager", "auto"))
        elif tool_name == "list_installed_packages":
            return await self._packages.list_installed(inp.get("manager", "auto"))
        elif tool_name == "pip_install":
            return await self._packages.pip_install(inp["package"], inp.get("user", True))
        elif tool_name == "npm_install":
            return await self._packages.npm_install(
                inp["package"], inp.get("global_", False), inp.get("cwd") or None
            )

        # --- ProcessManager ---
        elif tool_name == "list_processes":
            return self._processes.list_processes(
                inp.get("sort_by", "cpu"), inp.get("limit", 20)
            )
        elif tool_name == "find_process":
            return self._processes.find_process(inp["name"])
        elif tool_name == "get_process_info":
            return self._processes.get_process_info(inp["pid"])
        elif tool_name == "get_top_processes":
            return self._processes.get_top_processes(inp.get("limit", 5))
        elif tool_name == "kill_process_advanced":
            confirmed = await self._safety.confirm_destructive(
                "Завершение процесса (advanced)", f"PID: {inp['pid']} force={inp.get('force', False)}"
            )
            if not confirmed:
                return {"cancelled": True}
            return self._processes.kill(inp["pid"], inp.get("force", False))

        # --- ArchiveTool ---
        elif tool_name == "create_archive":
            self._safety.check_path(inp["source"])
            return self._archives.create_archive(
                inp["source"], inp["destination"], inp.get("format", "tar.gz")
            )
        elif tool_name == "extract_archive":
            self._safety.check_path(inp["source"])
            self._safety.check_path(inp["destination"])
            return self._archives.extract_archive(inp["source"], inp["destination"])
        elif tool_name == "list_archive":
            self._safety.check_path(inp["path"])
            return self._archives.list_archive(inp["path"])
        elif tool_name == "get_archive_size":
            self._safety.check_path(inp["path"])
            return self._archives.get_archive_size(inp["path"])

        # --- GitTool ---
        elif tool_name == "git_status":
            return await self._git.status(inp.get("cwd", "."))
        elif tool_name == "git_log":
            return await self._git.log(inp.get("cwd", "."), inp.get("limit", 10))
        elif tool_name == "git_commit":
            return await self._git.commit(
                inp["message"], inp.get("add_all", True), inp.get("cwd", ".")
            )
        elif tool_name == "git_push":
            return await self._git.push(
                inp.get("remote", "origin"), inp.get("branch", "") or None, inp.get("cwd", ".")
            )
        elif tool_name == "git_pull":
            return await self._git.pull(inp.get("remote", "origin"), inp.get("cwd", "."))
        elif tool_name == "git_clone":
            return await self._git.clone(inp["url"], inp.get("destination", "") or None)
        elif tool_name == "git_branch":
            return await self._git.branch(inp.get("cwd", "."))
        elif tool_name == "git_checkout":
            return await self._git.checkout(
                inp["branch"], inp.get("create", False), inp.get("cwd", ".")
            )
        elif tool_name == "git_diff":
            return await self._git.diff(inp.get("cwd", "."))

        # --- ServiceManager ---
        elif tool_name == "list_services":
            return await self._services.list_services(inp.get("status_filter", "all"))
        elif tool_name == "service_status":
            return await self._services.status(inp["name"])
        elif tool_name == "start_service":
            confirmed = await self._safety.confirm_sudo(f"systemctl start {inp['name']}")
            if not confirmed:
                return {"cancelled": True}
            return await self._services.start(inp["name"], self._sudo)
        elif tool_name == "stop_service":
            confirmed = await self._safety.confirm_sudo(f"systemctl stop {inp['name']}")
            if not confirmed:
                return {"cancelled": True}
            return await self._services.stop(inp["name"], self._sudo)
        elif tool_name == "restart_service":
            confirmed = await self._safety.confirm_sudo(f"systemctl restart {inp['name']}")
            if not confirmed:
                return {"cancelled": True}
            return await self._services.restart(inp["name"], self._sudo)
        elif tool_name == "enable_service":
            confirmed = await self._safety.confirm_sudo(f"systemctl enable {inp['name']}")
            if not confirmed:
                return {"cancelled": True}
            return await self._services.enable(inp["name"], self._sudo)
        elif tool_name == "disable_service":
            confirmed = await self._safety.confirm_sudo(f"systemctl disable {inp['name']}")
            if not confirmed:
                return {"cancelled": True}
            return await self._services.disable(inp["name"], self._sudo)
        elif tool_name == "get_service_logs":
            return await self._services.get_logs(inp["name"], inp.get("lines", 50))

        # --- AppManager ---
        elif tool_name == "open_application":
            return self._apps.open_application(
                inp["app_name"], inp.get("workspace", 1), inp.get("args")
            )
        elif tool_name == "close_application":
            confirmed = await self._safety.confirm_destructive(
                "Закрытие приложения", inp["identifier"]
            )
            if not confirmed:
                return {"cancelled": True}
            return self._apps.close_application(inp["identifier"])
        elif tool_name == "switch_workspace":
            return self._apps.switch_workspace(inp["workspace"])
        elif tool_name == "move_window_to_workspace":
            return self._apps.move_window_to_workspace(
                inp["window_title"], inp["workspace"]
            )
        elif tool_name == "list_open_applications":
            return self._apps.list_open_applications()

        # --- CronTool ---
        elif tool_name == "list_crons":
            return self._cron.list_crons(inp.get("user", "current"))
        elif tool_name == "add_cron":
            return self._cron.add_cron(
                inp["schedule"], inp["command"], inp.get("comment", "")
            )
        elif tool_name == "remove_cron":
            confirmed = await self._safety.confirm_destructive(
                "Удаление cron-задания", f"index: {inp['index']}"
            )
            if not confirmed:
                return {"cancelled": True}
            return self._cron.remove_cron(inp["index"])
        elif tool_name == "edit_cron":
            return self._cron.edit_cron(
                inp["index"], inp.get("schedule", ""), inp.get("command", "")
            )

        else:
            return {"error": f"Неизвестный инструмент: {tool_name}"}

    def format_result(self, result: Any) -> str:
        """Форматирует результат инструмента в строку для ИИ."""
        if isinstance(result, str):
            return result
        elif isinstance(result, bool):
            return "✅ Успешно" if result else "❌ Ошибка"
        elif isinstance(result, dict):
            if "error" in result:
                return f"❌ Ошибка: {result['error']}"
            if "cancelled" in result:
                return "⚠️ Операция отменена пользователем"
            return json.dumps(result, ensure_ascii=False, indent=2)
        elif isinstance(result, list):
            return json.dumps(result, ensure_ascii=False, indent=2)
        elif isinstance(result, int):
            return str(result)
        return str(result)
