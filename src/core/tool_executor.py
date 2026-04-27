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
from .safety import SafetyChecker, SafetyError

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
