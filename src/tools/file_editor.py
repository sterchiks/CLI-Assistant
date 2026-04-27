"""Инструмент для редактирования содержимого файлов."""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TEMPLATES = {
    "python_script": '#!/usr/bin/env python3\n"""Описание скрипта."""\n\n\ndef main() -> None:\n    pass\n\n\nif __name__ == "__main__":\n    main()\n',
    "bash_script": "#!/bin/bash\nset -euo pipefail\n\n# Описание скрипта\n\nmain() {\n    echo \"Hello, World!\"\n}\n\nmain \"$@\"\n",
    "json": '{\n  "key": "value"\n}\n',
    "yaml": "# YAML конфигурация\nkey: value\nlist:\n  - item1\n  - item2\n",
    "markdown": "# Заголовок\n\n## Описание\n\nТекст документа.\n",
    "html": "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>Страница</title>\n</head>\n<body>\n    <h1>Заголовок</h1>\n</body>\n</html>\n",
    "dockerfile": "FROM python:3.11-slim\n\nWORKDIR /app\n\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\n\nCOPY . .\n\nCMD [\"python\", \"main.py\"]\n",
}


class FileEditor:
    """Редактирование содержимого файлов."""

    def write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> bool:
        """Полностью перезаписывает файл новым содержимым."""
        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"write_file error: {e}")
            return False

    def append_to_file(self, path: str, content: str) -> bool:
        """Добавляет текст в конец файла."""
        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"append_to_file error: {e}")
            return False

    def insert_lines(
        self, path: str, line_number: int, content: str
    ) -> bool:
        """
        Вставляет строки в конкретную позицию (1-based).
        Вставка происходит ПЕРЕД указанной строкой.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"insert_lines: файл не найден: {path}")
                return False

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            insert_pos = max(0, min(line_number - 1, len(lines)))
            new_lines = content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"

            lines[insert_pos:insert_pos] = new_lines

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except Exception as e:
            logger.error(f"insert_lines error: {e}")
            return False

    def replace_in_file(
        self,
        path: str,
        old: str,
        new: str,
        all_occurrences: bool = True,
    ) -> int:
        """
        Заменяет текст в файле.
        Возвращает количество замен или -1 при ошибке.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"replace_in_file: файл не найден: {path}")
                return -1

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if all_occurrences:
                new_content = content.replace(old, new)
                count = content.count(old)
            else:
                new_content = content.replace(old, new, 1)
                count = 1 if old in content else 0

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return count
        except Exception as e:
            logger.error(f"replace_in_file error: {e}")
            return -1

    def replace_lines(
        self, path: str, start: int, end: int, new_content: str
    ) -> bool:
        """Заменяет диапазон строк (1-based) новым содержимым."""
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"replace_lines: файл не найден: {path}")
                return False

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = new_content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"

            lines[start - 1:end] = new_lines

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except Exception as e:
            logger.error(f"replace_lines error: {e}")
            return False

    def delete_lines(self, path: str, start: int, end: int) -> bool:
        """Удаляет диапазон строк из файла (1-based)."""
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"delete_lines: файл не найден: {path}")
                return False

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            del lines[start - 1:end]

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except Exception as e:
            logger.error(f"delete_lines error: {e}")
            return False

    def create_file(
        self,
        path: str,
        content: str = "",
        template: Optional[str] = None,
    ) -> bool:
        """
        Создаёт новый файл.
        template — опциональный шаблон: python_script, bash_script, json, yaml и т.д.
        """
        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():
                logger.warning(f"create_file: файл уже существует: {path}")

            if template and template in TEMPLATES:
                file_content = TEMPLATES[template]
            else:
                file_content = content

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            # Делаем bash скрипты исполняемыми
            if template == "bash_script":
                file_path.chmod(file_path.stat().st_mode | 0o111)

            return True
        except Exception as e:
            logger.error(f"create_file error: {e}")
            return False

    def create_backup(self, path: str) -> str:
        """
        Создаёт .bak копию файла с временной меткой.
        Возвращает путь к бэкапу или пустую строку при ошибке.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"create_backup: файл не найден: {path}")
                return ""

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".{timestamp}.bak")
            shutil.copy2(str(file_path), str(backup_path))
            return str(backup_path)
        except Exception as e:
            logger.error(f"create_backup error: {e}")
            return ""

    def restore_backup(self, backup_path: str) -> bool:
        """Восстанавливает файл из бэкапа."""
        try:
            bak_path = Path(backup_path).expanduser().resolve()
            if not bak_path.exists():
                logger.error(f"restore_backup: бэкап не найден: {backup_path}")
                return False

            # Определяем оригинальный путь (убираем .TIMESTAMP.bak)
            name = bak_path.name
            # Формат: filename.YYYYMMDD_HHMMSS.bak
            parts = name.rsplit(".", 3)
            if len(parts) >= 3 and parts[-1] == "bak":
                original_name = ".".join(parts[:-2])
            else:
                original_name = name.replace(".bak", "")

            original_path = bak_path.parent / original_name
            shutil.copy2(str(bak_path), str(original_path))
            return True
        except Exception as e:
            logger.error(f"restore_backup error: {e}")
            return False
