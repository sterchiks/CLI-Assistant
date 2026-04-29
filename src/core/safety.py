"""Модуль проверок безопасности перед выполнением операций."""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable
from fnmatch import fnmatch

logger = logging.getLogger(__name__)


# ─── Катастрофические команды ────────────────────────────────────────────────
#
# Это команды, которые уничтожают систему/пользовательские данные целиком и
# безвозвратно. Их выполнение блокируется НА УРОВНЕ КОДА — независимо от того,
# что попросил пользователь и что решила модель. Даже подтверждение их не
# разблокирует. Любой match → tool_executor возвращает фразу-отказ
# "НЕТ ИДИ НАХУЙ" и ничего не запускает.
#
# Каждая запись — это (regex, человекочитаемое описание).
# Регулярки нечувствительны к регистру и допускают произвольные пробелы.
# Цель — поймать наиболее распространённые формы катастрофических команд.
# Это НЕ полная защита от злонамеренного пользователя (любой shell позволяет
# обфускацию через переменные/eval/base64/и т.п.), но это надёжный заслон
# от случайного запуска по запросу вроде «удали всё» или галлюцинации модели.
CATASTROPHIC_COMMAND_PATTERNS: list[tuple[re.Pattern, str]] = [
    # rm -rf / в любых вариациях, включая --no-preserve-root и доп. флаги
    (
        re.compile(
            r"(?:^|[\s;&|`(])rm\s+(?:-[a-zA-Z]*[rRf][a-zA-Z]*\s+|--recursive\s+|--force\s+|--no-preserve-root\s+)+/(?:\s|$|\*)",
            re.IGNORECASE,
        ),
        "rm -rf / — удаление корневой файловой системы",
    ),
    # rm -rf /* (звёздочка после слэша) — отдельный паттерн на случай если
    # выше не зацепило (например `rm -rf /*` без пробела).
    (
        re.compile(r"\brm\s+-[a-zA-Z]*[rRf][a-zA-Z]*\s+/\*", re.IGNORECASE),
        "rm -rf /* — удаление всего содержимого корня",
    ),
    # rm -rf ~  / rm -rf $HOME / rm -rf "$HOME" / rm -rf ${HOME}
    # ВАЖНО: ловим ТОЛЬКО голую ссылку на домашнюю папку (без подпути).
    # `rm -rf ~/Downloads/junk` — это нормальная команда, она НЕ должна
    # блокироваться. Поэтому после ~/$HOME допускаем только конец строки или
    # shell-разделитель ;|&, но НЕ слэш.
    (
        re.compile(
            r"\brm\s+-[a-zA-Z]*[rRf][a-zA-Z]*\s+(?:~|\"~\"|'~'|\$HOME|\"\$HOME\"|'\$HOME'|\$\{HOME\})(?=\s*(?:$|[;&|]))",
            re.IGNORECASE,
        ),
        "rm -rf ~ — удаление домашней папки",
    ),

    # find / -delete  (и find / ... -exec rm)
    (
        re.compile(r"\bfind\s+/\s+(?:[^|;&]*\s)?(?:-delete|-exec\s+rm\b)", re.IGNORECASE),
        "find / -delete — массовое удаление от корня",
    ),
    # dd … of=/dev/sdX  /  of=/dev/nvmeX  / of=/dev/hdX  / of=/dev/disk
    (
        re.compile(
            r"\bdd\b[^|;&\n]*\bof=/dev/(?:sd[a-z]+\d*|nvme\d+n\d+(?:p\d+)?|hd[a-z]+\d*|mmcblk\d+(?:p\d+)?|disk\d+|vd[a-z]+\d*)\b",
            re.IGNORECASE,
        ),
        "dd of=/dev/* — затирание блочного устройства",
    ),
    # mkfs.* /dev/...
    (
        re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\s+[^|;&\n]*?/dev/[a-z]+\d*", re.IGNORECASE),
        "mkfs — форматирование блочного устройства",
    ),
    # > /dev/sda и аналоги: запись в blockdev через redirect
    (
        re.compile(
            r">\s*/dev/(?:sd[a-z]+\d*|nvme\d+n\d+(?:p\d+)?|hd[a-z]+\d*|mmcblk\d+(?:p\d+)?|vd[a-z]+\d*)\b",
            re.IGNORECASE,
        ),
        "> /dev/* — запись в блочное устройство",
    ),
    # fork bomb: :(){ :|:& };:  (с любыми пробелами)
    (
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
        "fork bomb",
    ),
    # chmod -R 000/777 /  (рекурсивный chmod от корня)
    (
        re.compile(r"\bchmod\s+-R\s+\S+\s+/(?:\s|$)", re.IGNORECASE),
        "chmod -R от корня",
    ),
    # chown -R … /
    (
        re.compile(r"\bchown\s+-R\s+\S+\s+/(?:\s|$)", re.IGNORECASE),
        "chown -R от корня",
    ),
    # mv ~ /dev/null  /  mv /home /dev/null
    (
        re.compile(
            r"\bmv\s+(?:~|\$HOME|\"\$HOME\"|/home(?:/[^\s]+)?)\s+/dev/null\b",
            re.IGNORECASE,
        ),
        "mv ~ /dev/null — уничтожение домашней папки",
    ),
    # curl/wget … | sh  /  | bash  (выполнение скрипта из интернета)
    (
        re.compile(
            r"\b(?:curl|wget)\b[^|;&\n]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b",
            re.IGNORECASE,
        ),
        "curl|sh / wget|sh — выполнение неизвестного скрипта из интернета",
    ),
]


# Жёсткая фраза, которой система отказывает на любой катастрофический запрос.
# Используется и в чате (как ответ tool-у), и в логах.
CATASTROPHIC_REFUSAL = "НЕТ ИДИ НАХУЙ"


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

    def is_yolo(self) -> bool:
        """Включён ли YOLO-режим (без подтверждений).

        В YOLO-режиме ассистент не спрашивает подтверждения у пользователя
        перед деструктивными и sudo-операциями. Хард-блок катастрофических
        команд (rm -rf /, dd of=/dev/sdX и т.п.) при этом **по-прежнему
        работает** — он реализован отдельно в `check_catastrophic_command`
        и проверяется в `tool_executor` до любых подтверждений.
        """
        if self._config:
            return bool(getattr(
                getattr(self._config, "safety", None), "yolo_mode", False
            ))
        return False

    def needs_destructive_confirm(self) -> bool:
        """Нужно ли подтверждение для деструктивных операций."""
        if self.is_yolo():
            return False
        if self._config:
            return getattr(
                getattr(self._config, "safety", None), "confirm_destructive", True
            )
        return True

    def needs_sudo_confirm(self) -> bool:
        """Нужно ли подтверждение для sudo операций."""
        if self.is_yolo():
            return False
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

    def check_catastrophic_command(self, command: str) -> Optional[str]:
        """Проверяет команду на КАТАСТРОФИЧНОСТЬ.

        В отличие от `check_dangerous_command`, такие команды НЕЛЬЗЯ выполнять
        даже с подтверждением — они уничтожают систему/диск/домашнюю папку
        безвозвратно. Если найден match — возвращается описание паттерна,
        который сработал. Решение «что делать дальше» принимает вызывающий
        (`tool_executor`): он останавливает выполнение и возвращает
        фразу-отказ `CATASTROPHIC_REFUSAL` модели.

        Возвращает:
            None — команда не катастрофична;
            str  — короткое описание сработавшего паттерна.
        """
        if not command:
            return None
        # Нормализуем: убираем повторяющиеся пробелы вокруг ключевых символов,
        # чтобы лучше ловить варианты типа "rm  -rf  /" с двойными пробелами.
        # На сами регулярки это не влияет, но логи становятся читаемее.
        cmd = command
        for pattern, description in CATASTROPHIC_COMMAND_PATTERNS:
            if pattern.search(cmd):
                logger.warning(
                    "Заблокирована катастрофическая команда: %r (паттерн: %s)",
                    command, description,
                )
                return description
        return None

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
