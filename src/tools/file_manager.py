"""Инструмент для управления файлами и директориями."""

import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileManager:
    """Операции с файлами и директориями."""

    def copy_file(self, src: str, dst: str, overwrite: bool = False) -> bool:
        """Копирует файл из src в dst."""
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser()

            if not src_path.exists():
                logger.error(f"copy_file: источник не найден: {src}")
                return False
            if not src_path.is_file():
                logger.error(f"copy_file: {src} не является файлом")
                return False
            if dst_path.exists() and not overwrite:
                logger.error(f"copy_file: файл уже существует: {dst}")
                return False

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
            return True
        except Exception as e:
            logger.error(f"copy_file error: {e}")
            return False

    def move_file(self, src: str, dst: str) -> bool:
        """Перемещает файл из src в dst."""
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser()

            if not src_path.exists():
                logger.error(f"move_file: источник не найден: {src}")
                return False

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            return True
        except Exception as e:
            logger.error(f"move_file error: {e}")
            return False

    def delete_file(self, path: str, secure: bool = False) -> bool:
        """
        Удаляет файл.
        secure=True использует shred-подобное затирание (перезапись нулями).
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                logger.error(f"delete_file: файл не найден: {path}")
                return False
            if not file_path.is_file():
                logger.error(f"delete_file: {path} не является файлом")
                return False

            if secure:
                self._secure_delete(file_path)
            else:
                file_path.unlink()
            return True
        except Exception as e:
            logger.error(f"delete_file error: {e}")
            return False

    def _secure_delete(self, path: Path) -> None:
        """Безопасное удаление: перезапись нулями перед удалением."""
        try:
            # Пробуем shred если доступен
            result = subprocess.run(
                ["shred", "-u", "-z", str(path)],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: ручная перезапись
        size = path.stat().st_size
        with open(path, "wb") as f:
            f.write(b"\x00" * size)
            f.flush()
            os.fsync(f.fileno())
        path.unlink()

    def create_directory(self, path: str, parents: bool = True) -> bool:
        """Создаёт директорию."""
        try:
            dir_path = Path(path).expanduser()
            dir_path.mkdir(parents=parents, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"create_directory error: {e}")
            return False

    def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """
        Удаляет директорию.
        recursive=True удаляет со всем содержимым.
        ВАЖНО: вызывающий код должен запросить подтверждение перед вызовом с recursive=True.
        """
        try:
            dir_path = Path(path).expanduser().resolve()
            if not dir_path.exists():
                logger.error(f"delete_directory: директория не найдена: {path}")
                return False
            if not dir_path.is_dir():
                logger.error(f"delete_directory: {path} не является директорией")
                return False

            if recursive:
                shutil.rmtree(str(dir_path))
            else:
                dir_path.rmdir()  # Удаляет только пустую директорию
            return True
        except OSError as e:
            logger.error(f"delete_directory error: {e}")
            return False

    def copy_directory(self, src: str, dst: str) -> bool:
        """Копирует директорию рекурсивно."""
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser()

            if not src_path.exists():
                logger.error(f"copy_directory: источник не найден: {src}")
                return False
            if not src_path.is_dir():
                logger.error(f"copy_directory: {src} не является директорией")
                return False

            shutil.copytree(str(src_path), str(dst_path))
            return True
        except Exception as e:
            logger.error(f"copy_directory error: {e}")
            return False

    def rename(self, path: str, new_name: str) -> bool:
        """Переименовывает файл или директорию."""
        try:
            old_path = Path(path).expanduser().resolve()
            if not old_path.exists():
                logger.error(f"rename: путь не найден: {path}")
                return False

            new_path = old_path.parent / new_name
            old_path.rename(new_path)
            return True
        except Exception as e:
            logger.error(f"rename error: {e}")
            return False

    def set_permissions(
        self, path: str, mode: str, recursive: bool = False
    ) -> bool:
        """
        Устанавливает права доступа.
        mode — строка типа '755' или 'rwxr-xr-x'.
        """
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                logger.error(f"set_permissions: путь не найден: {path}")
                return False

            # Парсим mode
            if mode.isdigit():
                oct_mode = int(mode, 8)
            else:
                oct_mode = self._parse_symbolic_mode(mode)

            if recursive and target.is_dir():
                for item in target.rglob("*"):
                    item.chmod(oct_mode)
            target.chmod(oct_mode)
            return True
        except Exception as e:
            logger.error(f"set_permissions error: {e}")
            return False

    def _parse_symbolic_mode(self, mode: str) -> int:
        """Парсит символьный режим прав (rwxr-xr-x) в числовой."""
        if len(mode) != 9:
            raise ValueError(f"Неверный формат прав: {mode}")
        result = 0
        bits = [
            (0o400, "r"), (0o200, "w"), (0o100, "x"),
            (0o040, "r"), (0o020, "w"), (0o010, "x"),
            (0o004, "r"), (0o002, "w"), (0o001, "x"),
        ]
        for i, (bit, char) in enumerate(bits):
            if mode[i] == char:
                result |= bit
        return result

    def set_owner(
        self,
        path: str,
        user: str,
        group: str = "",
        recursive: bool = False,
    ) -> bool:
        """Устанавливает владельца файла/директории (требует прав)."""
        try:
            import pwd, grp as grp_module

            uid = pwd.getpwnam(user).pw_uid
            gid = grp_module.getgrnam(group).gr_gid if group else -1

            target = Path(path).expanduser().resolve()
            if not target.exists():
                return False

            os.chown(str(target), uid, gid)
            if recursive and target.is_dir():
                for item in target.rglob("*"):
                    os.chown(str(item), uid, gid)
            return True
        except Exception as e:
            logger.error(f"set_owner error: {e}")
            return False

    def create_symlink(self, target: str, link_path: str) -> bool:
        """Создаёт символическую ссылку."""
        try:
            target_path = Path(target).expanduser()
            link = Path(link_path).expanduser()
            link.symlink_to(target_path)
            return True
        except Exception as e:
            logger.error(f"create_symlink error: {e}")
            return False

    def get_disk_usage(self, path: str) -> dict:
        """Возвращает использование диска для пути."""
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return {"error": f"Путь не найден: {path}"}

            usage = shutil.disk_usage(str(target))
            return {
                "path": str(target),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "total_human": self._human_size(usage.total),
                "used_human": self._human_size(usage.used),
                "free_human": self._human_size(usage.free),
                "percent_used": round(usage.used / usage.total * 100, 1),
            }
        except Exception as e:
            logger.error(f"get_disk_usage error: {e}")
            return {"error": str(e)}

    @staticmethod
    def _human_size(size: int) -> str:
        """Конвертирует байты в читаемый формат."""
        for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ПБ"
