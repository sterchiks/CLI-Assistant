"""Инструмент для чтения файлов и директорий."""

import os
import re
import stat
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FileReader:
    """Инструменты для чтения файлов и получения информации о них."""

    CHUNK_SIZE = 65536  # 64KB чанки для больших файлов

    def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """
        Читает содержимое текстового файла.
        Поддерживает большие файлы через чтение по чанкам.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return f"Ошибка: файл не найден: {path}"
            if not file_path.is_file():
                return f"Ошибка: {path} не является файлом"

            chunks = []
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                while True:
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
            return "".join(chunks)
        except PermissionError:
            return f"Ошибка: нет прав на чтение файла: {path}"
        except UnicodeDecodeError:
            return f"Ошибка: не удалось декодировать файл как {encoding}. Попробуйте другую кодировку."
        except Exception as e:
            logger.error(f"read_file error: {e}")
            return f"Ошибка чтения файла: {e}"

    def read_file_lines(self, path: str, start: int, end: int) -> str:
        """
        Читает диапазон строк файла (1-based индексация).
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return f"Ошибка: файл не найден: {path}"

            lines = []
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if i > end:
                        break
                    if i >= start:
                        lines.append(f"{i:4d} | {line}")

            if not lines:
                return f"Строки {start}-{end} не найдены в файле"
            return "".join(lines)
        except Exception as e:
            logger.error(f"read_file_lines error: {e}")
            return f"Ошибка: {e}"

    def get_file_info(self, path: str) -> dict:
        """
        Возвращает метаданные файла: размер, дата изменения, права, тип, владелец.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return {"error": f"Файл не найден: {path}"}

            st = file_path.stat()
            mode = stat.filemode(st.st_mode)

            # Определяем тип файла
            if file_path.is_dir():
                file_type = "directory"
            elif file_path.is_symlink():
                file_type = "symlink"
            elif file_path.is_file():
                file_type = "file"
            else:
                file_type = "other"

            # Владелец (Unix)
            owner = "unknown"
            group = "unknown"
            try:
                import pwd, grp
                owner = pwd.getpwuid(st.st_uid).pw_name
                group = grp.getgrgid(st.st_gid).gr_name
            except (ImportError, KeyError):
                owner = str(st.st_uid)
                group = str(st.st_gid)

            return {
                "path": str(file_path),
                "name": file_path.name,
                "type": file_type,
                "size": st.st_size,
                "size_human": self._human_size(st.st_size),
                "permissions": mode,
                "owner": owner,
                "group": group,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(st.st_ctime).isoformat(),
                "accessed": datetime.fromtimestamp(st.st_atime).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_file_info error: {e}")
            return {"error": str(e)}

    def list_directory(
        self,
        path: str,
        show_hidden: bool = False,
        recursive: bool = False,
    ) -> list[dict]:
        """
        Возвращает список файлов и папок в директории.
        """
        try:
            dir_path = Path(path).expanduser().resolve()
            if not dir_path.exists():
                return [{"error": f"Директория не найдена: {path}"}]
            if not dir_path.is_dir():
                return [{"error": f"{path} не является директорией"}]

            results = []
            self._list_dir_recursive(dir_path, show_hidden, recursive, results, depth=0)
            return results
        except PermissionError:
            return [{"error": f"Нет прав на чтение директории: {path}"}]
        except Exception as e:
            logger.error(f"list_directory error: {e}")
            return [{"error": str(e)}]

    def _list_dir_recursive(
        self,
        path: Path,
        show_hidden: bool,
        recursive: bool,
        results: list,
        depth: int,
        max_depth: int = 5,
    ) -> None:
        """Рекурсивный обход директории."""
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for entry in entries:
                if not show_hidden and entry.name.startswith("."):
                    continue
                try:
                    st = entry.stat()
                    item = {
                        "name": entry.name,
                        "path": str(entry),
                        "type": "dir" if entry.is_dir() else "file",
                        "size": st.st_size if entry.is_file() else 0,
                        "size_human": self._human_size(st.st_size) if entry.is_file() else "-",
                        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "depth": depth,
                    }
                    results.append(item)
                    if recursive and entry.is_dir():
                        self._list_dir_recursive(
                            entry, show_hidden, recursive, results, depth + 1, max_depth
                        )
                except PermissionError:
                    results.append({
                        "name": entry.name,
                        "path": str(entry),
                        "type": "unknown",
                        "error": "нет прав",
                        "depth": depth,
                    })
        except PermissionError:
            pass

    def search_in_file(
        self, path: str, pattern: str, regex: bool = False
    ) -> list[dict]:
        """
        Ищет текст или regex-паттерн в файле.
        Возвращает список совпадений с номерами строк.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return [{"error": f"Файл не найден: {path}"}]

            results = []
            if regex:
                compiled = re.compile(pattern)
            else:
                compiled = None

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    if regex and compiled:
                        if compiled.search(line):
                            results.append({
                                "line": line_num,
                                "content": line.rstrip("\n"),
                            })
                    else:
                        if pattern.lower() in line.lower():
                            results.append({
                                "line": line_num,
                                "content": line.rstrip("\n"),
                            })
            return results
        except re.error as e:
            return [{"error": f"Неверный regex: {e}"}]
        except Exception as e:
            logger.error(f"search_in_file error: {e}")
            return [{"error": str(e)}]

    def search_files(
        self,
        directory: str,
        pattern: str,
        file_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Ищет файлы по имени/расширению/паттерну в директории.
        file_type: 'file', 'dir' или None для обоих.
        """
        try:
            dir_path = Path(directory).expanduser().resolve()
            if not dir_path.exists():
                return [{"error": f"Директория не найдена: {directory}"}]

            results = []
            # Используем glob для поиска
            for entry in dir_path.rglob(pattern):
                if file_type == "file" and not entry.is_file():
                    continue
                if file_type == "dir" and not entry.is_dir():
                    continue
                try:
                    st = entry.stat()
                    results.append({
                        "name": entry.name,
                        "path": str(entry),
                        "type": "dir" if entry.is_dir() else "file",
                        "size_human": self._human_size(st.st_size) if entry.is_file() else "-",
                        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception:
                    results.append({"name": entry.name, "path": str(entry)})

            return results if results else [{"info": "Файлы не найдены"}]
        except Exception as e:
            logger.error(f"search_files error: {e}")
            return [{"error": str(e)}]

    @staticmethod
    def _human_size(size: int) -> str:
        """Конвертирует байты в читаемый формат."""
        for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ПБ"
