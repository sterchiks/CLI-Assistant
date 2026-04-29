"""Менеджер sudo операций с безопасным кэшированием пароля в памяти."""

import asyncio
import logging
import subprocess
import time
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class SudoManager:
    """
    Управляет sudo операциями.
    Пароль кэшируется ТОЛЬКО в памяти процесса, НЕ на диске.
    """

    def __init__(self, cache_minutes: int = 15) -> None:
        self._password: Optional[str] = None
        self._cache_time: float = 0.0
        self._cache_minutes = cache_minutes
        # Callback для запроса пароля через UI
        self._password_callback: Optional[Callable[[], Awaitable[str]]] = None

    def set_password_callback(self, callback: Callable[[], Awaitable[str]]) -> None:
        """Устанавливает callback для запроса пароля через UI."""
        self._password_callback = callback

    def set_cache_minutes(self, minutes: int) -> None:
        """Устанавливает время кэширования пароля."""
        self._cache_minutes = minutes

    def _is_cache_valid(self) -> bool:
        """Проверяет, не истёк ли кэш пароля."""
        if self._password is None:
            return False
        elapsed = time.time() - self._cache_time
        return elapsed < (self._cache_minutes * 60)

    async def request_sudo_password(self) -> bool:
        """
        Безопасно запрашивает пароль sudo через UI callback.
        Кэширует в памяти сессии на cache_minutes минут.
        Возвращает True если пароль получен и валиден.
        """
        if self._is_cache_valid():
            return True

        password = ""
        if self._password_callback:
            try:
                password = await self._password_callback()
            except Exception as e:
                logger.error(f"Ошибка получения пароля: {e}")
                return False
        else:
            # Fallback: консольный ввод
            import getpass
            try:
                password = getpass.getpass("Пароль sudo: ")
            except (KeyboardInterrupt, EOFError):
                return False

        if not password:
            return False

        # Проверяем пароль
        if await self._verify_password(password):
            self._password = password
            self._cache_time = time.time()
            return True
        else:
            logger.warning("Неверный пароль sudo")
            return False

    async def _verify_password(self, password: str) -> bool:
        """Проверяет пароль sudo через echo | sudo -S true."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "sudo", "-S", "-k", "true",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=(password + "\n").encode()),
                timeout=10.0,
            )
            return proc.returncode == 0
        except asyncio.TimeoutError:
            logger.error("Таймаут проверки пароля sudo")
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки пароля sudo: {e}")
            return False

    def clear_sudo_cache(self) -> bool:
        """Очищает кэш пароля из памяти."""
        self._password = None
        self._cache_time = 0.0
        # Также сбрасываем sudo credentials в системе
        try:
            subprocess.run(["sudo", "-k"], capture_output=True, timeout=5)
        except Exception:
            pass
        return True

    def check_sudo_available(self) -> bool:
        """Проверяет наличие sudo прав у пользователя."""
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
        except Exception:
            return False

    async def run_as_root(self, command: str) -> dict:
        """
        Выполняет команду с правами root используя кэшированный пароль.
        Возвращает dict с stdout, stderr, returncode.
        """
        if not self._is_cache_valid():
            success = await self.request_sudo_password()
            if not success:
                return {
                    "stdout": "",
                    "stderr": "Не удалось получить пароль sudo",
                    "returncode": 1,
                }

        try:
            password = self._password or ""
            proc = await asyncio.create_subprocess_exec(
                "sudo", "-S", "bash", "-c", command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=(password + "\n").encode()),
                timeout=60.0,
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode or 0,
            }
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": "Таймаут выполнения команды",
                "returncode": 124,
            }
        except Exception as e:
            logger.error(f"run_as_root error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
            }

    def get_cache_remaining_seconds(self) -> int:
        """Возвращает оставшееся время кэша в секундах."""
        if not self._is_cache_valid():
            return 0
        elapsed = time.time() - self._cache_time
        remaining = (self._cache_minutes * 60) - elapsed
        return max(0, int(remaining))
