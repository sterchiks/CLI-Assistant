"""Инструмент для управления терминалами и выполнения команд."""

import asyncio
import logging
import os
import platform
import subprocess
import sys
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


class TerminalManager:
    """Управление терминалами и выполнение команд в subprocess."""

    # Известные эмуляторы терминала по платформам
    LINUX_TERMINALS = [
        "gnome-terminal", "konsole", "xfce4-terminal", "xterm",
        "alacritty", "kitty", "tilix", "terminator", "urxvt",
    ]

    async def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        capture_output: bool = True,
    ) -> dict:
        """
        Выполняет команду в отдельном subprocess.
        НЕ запускает команды в том же терминале где работает ассистент.
        Возвращает dict с stdout, stderr, returncode.
        """
        try:
            work_dir = os.path.expanduser(cwd) if cwd else None

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=work_dir,
                env=os.environ.copy(),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "stdout": "",
                    "stderr": f"Команда превысила таймаут {timeout}с",
                    "returncode": 124,
                    "timed_out": True,
                }

            return {
                "stdout": stdout.decode("utf-8", errors="replace") if stdout else "",
                "stderr": stderr.decode("utf-8", errors="replace") if stderr else "",
                "returncode": proc.returncode or 0,
                "timed_out": False,
            }
        except FileNotFoundError as e:
            return {
                "stdout": "",
                "stderr": f"Команда не найдена: {e}",
                "returncode": 127,
                "timed_out": False,
            }
        except Exception as e:
            logger.error(f"run_command error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "timed_out": False,
            }

    async def run_command_sudo(self, command: str, password: str) -> dict:
        """
        Выполняет команду с sudo.
        Пароль передаётся через stdin (sudo -S).
        """
        try:
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
            return {"stdout": "", "stderr": "Таймаут", "returncode": 124}
        except Exception as e:
            logger.error(f"run_command_sudo error: {e}")
            return {"stdout": "", "stderr": str(e), "returncode": 1}

    def open_terminal(
        self,
        terminal_emulator: Optional[str] = None,
        command: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> bool:
        """
        Открывает новое окно терминала.
        Автоопределяет доступный эмулятор если не указан.
        """
        system = platform.system()
        work_dir = os.path.expanduser(cwd) if cwd else None

        try:
            return self._open_linux_terminal(terminal_emulator, command, work_dir)
        except Exception as e:
            logger.error(f"open_terminal error: {e}")
            return False

    def _open_linux_terminal(
        self,
        preferred: Optional[str],
        command: Optional[str],
        cwd: Optional[str],
    ) -> bool:
        """Открывает терминал на Linux."""
        terminals_to_try = []
        if preferred:
            terminals_to_try.append(preferred)
        terminals_to_try.extend(self.LINUX_TERMINALS)

        for term in terminals_to_try:
            try:
                if subprocess.run(["which", term], capture_output=True).returncode != 0:
                    continue

                args = [term]
                if command:
                    if term == "gnome-terminal":
                        args += ["--", "bash", "-c", f"{command}; exec bash"]
                    elif term in ("konsole", "xfce4-terminal", "tilix"):
                        args += ["-e", f"bash -c '{command}; exec bash'"]
                    elif term in ("alacritty", "kitty"):
                        args += ["-e", "bash", "-c", f"{command}; exec bash"]
                    else:
                        args += ["-e", f"bash -c '{command}; exec bash'"]

                subprocess.Popen(args, cwd=cwd, start_new_session=True)
                return True
            except Exception:
                continue
        return False

    def run_in_new_terminal(
        self,
        command: str,
        title: str = "CLI Assistant",
        keep_open: bool = True,
    ) -> bool:
        """Запускает команду в новом окне терминала."""
        try:
            suffix = "; exec bash" if keep_open else ""
            full_cmd = f"{command}{suffix}"
            for term in self.LINUX_TERMINALS:
                    if subprocess.run(["which", term], capture_output=True).returncode != 0:
                        continue
                    try:
                        if term == "gnome-terminal":
                            args = ["gnome-terminal", "--title", title, "--", "bash", "-c", full_cmd]
                        elif term == "xterm":
                            args = ["xterm", "-title", title, "-e", f"bash -c '{full_cmd}'"]
                        else:
                            args = [term, "-e", f"bash -c '{full_cmd}'"]
                        subprocess.Popen(args, start_new_session=True)
                        return True
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"run_in_new_terminal error: {e}")
        return False

    def get_running_processes(self) -> list[dict]:
        """Возвращает список запущенных процессов (аналог ps aux)."""
        processes = []
        try:
            for proc in psutil.process_iter(
                ["pid", "name", "username", "cpu_percent", "memory_percent", "status", "cmdline"]
            ):
                try:
                    info = proc.info
                    processes.append({
                        "pid": info["pid"],
                        "name": info["name"] or "",
                        "user": info["username"] or "",
                        "cpu": round(info["cpu_percent"] or 0, 1),
                        "mem": round(info["memory_percent"] or 0, 1),
                        "status": info["status"] or "",
                        "cmd": " ".join(info["cmdline"] or [])[:100],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"get_running_processes error: {e}")
        return processes

    def kill_process(self, pid: int, signal: str = "TERM") -> bool:
        """Завершает процесс по PID."""
        try:
            proc = psutil.Process(pid)
            if signal.upper() == "KILL":
                proc.kill()
            else:
                proc.terminate()
            return True
        except psutil.NoSuchProcess:
            logger.error(f"kill_process: процесс {pid} не найден")
            return False
        except psutil.AccessDenied:
            logger.error(f"kill_process: нет прав для завершения процесса {pid}")
            return False
        except Exception as e:
            logger.error(f"kill_process error: {e}")
            return False

    def get_system_info(self) -> dict:
        """Возвращает системную информацию: OS, CPU, RAM, uptime, hostname, user."""
        try:
            import socket
            from datetime import datetime, timedelta

            cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            boot_time = psutil.boot_time()
            uptime_seconds = int(psutil.time.time() - boot_time)
            uptime = str(timedelta(seconds=uptime_seconds))

            disk = psutil.disk_usage("/")

            return {
                "os": platform.system(),
                "os_version": platform.version(),
                "hostname": socket.gethostname(),
                "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": cpu_percent,
                "ram_total": mem.total,
                "ram_used": mem.used,
                "ram_free": mem.available,
                "ram_percent": mem.percent,
                "ram_total_human": self._human_size(mem.total),
                "ram_used_human": self._human_size(mem.used),
                "disk_total_human": self._human_size(disk.total),
                "disk_used_human": self._human_size(disk.used),
                "disk_free_human": self._human_size(disk.free),
                "disk_percent": disk.percent,
                "uptime": uptime,
                "python_version": sys.version.split()[0],
            }
        except Exception as e:
            logger.error(f"get_system_info error: {e}")
            return {"error": str(e)}

    @staticmethod
    def _human_size(size: int) -> str:
        """Конвертирует байты в читаемый формат."""
        for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ПБ"
