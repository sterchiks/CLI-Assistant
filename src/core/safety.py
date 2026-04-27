"""Модуль проверок безопасности перед выполнением операций."""

import os
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable
from fnmatch import fnmatch

logger = logging.getLogger(__name__)

# Абсолютно защищённые пути (нельзя изменить через конфиг)
HARDCODED_BLOCKED_PATHS = [
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
]

HARDCODED_BLOCKED_PATTERNS = [
    "/boot/*",
    "/dev/*",
    "/proc/*",
    "/sys/*",
]


class SafetyError(Exception):
    """Исключение при нарушении правил безопасности."""
    pass


class SafetyChecker:
    """Проверяет безопасность операций перед выполнением."""

    def __init__(self, config: Optional[object] = None) -> None:
        self._config = config
        # Callback для запроса подтверждения у пользователя
        self._confirm_callback: Optional[Callable[[str, str], Awaitable[bool]]] = None

    def set_confirm_callback(self, callback: Callable[[str, str], Awaitable[bool]]) -> None:
        """Устанавливает callback для запроса подтверждения."""
        self._confirm_callback = callback

    def update_config(self, config: object) -> None:
        """Обновляет конфигурацию."""
        self._config = config

    def is_path_blocked(self, path: str) -> bool:
        """Проверяет, заблокирован ли путь."""
        resolved = str(Path(path).resolve())

        # Проверка хардкодных путей
        for blocked in HARDCODED_BLOCKED_PATHS:
            if resolved == blocked or resolved.startswith(blocked + "/"):
                return True

        # Проверка хардкодных паттернов
        for pattern in HARDCODED_BLOCKED_PATTERNS:
            if fnmatch(resolved, pattern):
                return True

        # Проверка путей из конфига
        if self._config:
            blocked_paths = getattr(
                getattr(self._config, "safety", None), "blocked_paths", []
            )
            for blocked in blocked_paths:
                b_resolved = str(Path(blocked).resolve())
                if resolved == b_resolved or resolved.startswith(b_resolved + "/"):
                    return True

        return False

    def check_path(self, path: str) -> None:
        """Выбрасывает SafetyError если путь заблокирован."""
        if self.is_path_blocked(path):
            raise SafetyError(f"Путь заблокирован настройками безопасности: {path}")

    def check_file_size(self, path: str) -> None:
        """Проверяет размер файла."""
        max_mb = 50
        if self._config:
            max_mb = getattr(
                getattr(self._config, "safety", None), "max_file_size_mb", 50
            )
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > max_mb:
                raise SafetyError(
                    f"Файл слишком большой: {size_mb:.1f} МБ (максимум {max_mb} МБ)"
                )
        except OSError:
            pass  # Файл не существует — пусть другой код обработает

    def needs_destructive_confirm(self) -> bool:
        """Нужно ли подтверждение для деструктивных операций."""
        if self._config:
            return getattr(
                getattr(self._config, "safety", None), "confirm_destructive", True
            )
        return True

    def needs_sudo_confirm(self) -> bool:
        """Нужно ли подтверждение для sudo операций."""
        if self._config:
            return getattr(
                getattr(self._config, "safety", None), "confirm_sudo", True
            )
        return True

    def is_sudo_command_allowed(self, command: str) -> bool:
        """Проверяет, разрешена ли sudo команда (whitelist)."""
        if self._config:
            allowed = getattr(
                getattr(self._config, "safety", None), "allowed_sudo_commands", []
            )
            if allowed:  # Если whitelist не пустой — проверяем
                return any(command.startswith(cmd) for cmd in allowed)
        return True  # Пустой whitelist = всё разрешено

    def check_dangerous_command(self, command: str) -> Optional[str]:
        """
        Проверяет команду на опасность.
        Возвращает строку с предупреждением или None если безопасно.
        """
        dangerous_patterns = [
            ("rm -rf /", "Удаление корневой файловой системы"),
            ("rm -rf /*", "Удаление всего содержимого корня"),
            ("dd if=/dev/zero of=/dev/", "Затирание блочного устройства"),
            ("mkfs.", "Форматирование раздела"),
            ("> /dev/sda", "Запись в блочное устройство"),
            ("chmod -R 777 /", "Изменение прав на всю файловую систему"),
            ("chown -R", "Рекурсивное изменение владельца"),
            (":(){:|:&};:", "Fork bomb"),
            ("wget -O- | sh", "Выполнение скрипта из интернета"),
            ("curl | sh", "Выполнение скрипта из интернета"),
        ]

        cmd_lower = command.lower().strip()
        for pattern, description in dangerous_patterns:
            if pattern.lower() in cmd_lower:
                return f"⚠️ Опасная команда: {description}"

        return None

    async def confirm_destructive(self, action: str, details: str) -> bool:
        """
        Запрашивает подтверждение деструктивного действия.
        Возвращает True если пользователь подтвердил.
        """
        if not self.needs_destructive_confirm():
            return True

        if self._confirm_callback:
            return await self._confirm_callback(action, details)

        # Fallback: консольный ввод
        print(f"\n⚠️  {action}")
        print(f"   {details}")
        answer = input("Продолжить? [y/N]: ").strip().lower()
        return answer in ("y", "yes", "да", "д")

    async def confirm_sudo(self, command: str) -> bool:
        """Запрашивает подтверждение sudo операции."""
        if not self.needs_sudo_confirm():
            return True

        if self._confirm_callback:
            return await self._confirm_callback(
                "ПОДТВЕРЖДЕНИЕ SUDO",
                f"Команда: {command}"
            )

        print(f"\n⚠️  Требуются права администратора")
        print(f"   Команда: {command}")
        answer = input("Продолжить? [y/N]: ").strip().lower()
        return answer in ("y", "yes", "да", "д")


# Глобальный экземпляр
_safety_checker: Optional[SafetyChecker] = None


def get_safety_checker() -> SafetyChecker:
    """Возвращает глобальный экземпляр SafetyChecker."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = SafetyChecker()
    return _safety_checker
