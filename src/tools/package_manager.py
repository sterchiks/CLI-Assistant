"""Менеджер пакетов: apt/dnf/pacman/brew + pip + npm."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


SYSTEM_MANAGERS = ["apt", "apt-get", "dnf", "yum", "pacman", "zypper", "brew", "apk"]


class PackageManager:
    """Менеджер пакетов системы и языков программирования."""

    def detect_package_manager(self) -> str:
        """Автоопределение системного менеджера пакетов."""
        system = platform.system().lower()
        if system == "darwin":
            if shutil.which("brew"):
                return "brew"
        if system == "windows":
            if shutil.which("winget"):
                return "winget"
            if shutil.which("choco"):
                return "choco"
        for mgr in ["apt", "dnf", "pacman", "zypper", "yum", "apk", "brew"]:
            if shutil.which(mgr):
                return mgr
        return "unknown"

    # ---------- внутренние помощники ----------

    def _run(self, cmd: list[str], timeout: int = 600) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-4000:],
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Таймаут выполнения: {' '.join(cmd)}"}
        except FileNotFoundError:
            return {"error": f"Команда не найдена: {cmd[0]}"}
        except Exception as e:
            return {"error": f"_run error: {e}"}

    def _resolve_manager(self, manager: str) -> str:
        if manager == "auto":
            return self.detect_package_manager()
        return manager

    def _needs_sudo(self, manager: str) -> bool:
        if platform.system().lower() in ("darwin", "windows"):
            return False
        return manager in {"apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk"}

    # ---------- основные функции ----------

    def install_package(self, package: str, manager: str = "auto") -> dict[str, Any]:
        """Установить пакет (требует sudo для системных менеджеров)."""
        m = self._resolve_manager(manager)
        if m == "unknown":
            return {"error": "Не найден ни один поддерживаемый менеджер пакетов"}

        cmd_map = {
            "apt": ["apt-get", "install", "-y", package],
            "apt-get": ["apt-get", "install", "-y", package],
            "dnf": ["dnf", "install", "-y", package],
            "yum": ["yum", "install", "-y", package],
            "pacman": ["pacman", "-S", "--noconfirm", package],
            "zypper": ["zypper", "install", "-y", package],
            "brew": ["brew", "install", package],
            "apk": ["apk", "add", package],
            "winget": ["winget", "install", "--silent", package],
            "choco": ["choco", "install", "-y", package],
        }
        cmd = cmd_map.get(m)
        if cmd is None:
            return {"error": f"Менеджер {m} не поддерживается"}

        if self._needs_sudo(m):
            return {
                "requires_sudo": True,
                "manager": m,
                "command": " ".join(cmd),
                "message": "Установка требует sudo. Используй run_as_root.",
            }
        return self._run(cmd)

    def remove_package(self, package: str, manager: str = "auto") -> dict[str, Any]:
        """Удалить пакет."""
        m = self._resolve_manager(manager)
        if m == "unknown":
            return {"error": "Не найден менеджер пакетов"}

        cmd_map = {
            "apt": ["apt-get", "remove", "-y", package],
            "apt-get": ["apt-get", "remove", "-y", package],
            "dnf": ["dnf", "remove", "-y", package],
            "yum": ["yum", "remove", "-y", package],
            "pacman": ["pacman", "-R", "--noconfirm", package],
            "zypper": ["zypper", "remove", "-y", package],
            "brew": ["brew", "uninstall", package],
            "apk": ["apk", "del", package],
            "winget": ["winget", "uninstall", "--silent", package],
            "choco": ["choco", "uninstall", "-y", package],
        }
        cmd = cmd_map.get(m)
        if cmd is None:
            return {"error": f"Менеджер {m} не поддерживается"}

        if self._needs_sudo(m):
            return {
                "requires_sudo": True,
                "manager": m,
                "command": " ".join(cmd),
            }
        return self._run(cmd)

    def update_packages(self, manager: str = "auto") -> dict[str, Any]:
        """Обновить все пакеты."""
        m = self._resolve_manager(manager)
        if m == "unknown":
            return {"error": "Не найден менеджер пакетов"}

        cmd_map = {
            "apt": "apt-get update && apt-get upgrade -y",
            "apt-get": "apt-get update && apt-get upgrade -y",
            "dnf": "dnf upgrade -y",
            "yum": "yum update -y",
            "pacman": "pacman -Syu --noconfirm",
            "zypper": "zypper update -y",
            "brew": "brew update && brew upgrade",
            "apk": "apk update && apk upgrade",
            "winget": "winget upgrade --all --silent",
            "choco": "choco upgrade all -y",
        }
        cmd_str = cmd_map.get(m)
        if cmd_str is None:
            return {"error": f"Менеджер {m} не поддерживается"}

        if self._needs_sudo(m):
            return {
                "requires_sudo": True,
                "manager": m,
                "command": cmd_str,
                "message": "Обновление требует sudo. Используй run_as_root.",
            }
        try:
            proc = subprocess.run(
                cmd_str, shell=True, capture_output=True, text=True, timeout=1800
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-4000:],
            }
        except Exception as e:
            return {"error": f"update_packages error: {e}"}

    def search_package(self, query: str, manager: str = "auto") -> dict[str, Any]:
        """Поиск пакетов."""
        m = self._resolve_manager(manager)
        cmd_map = {
            "apt": ["apt-cache", "search", query],
            "apt-get": ["apt-cache", "search", query],
            "dnf": ["dnf", "search", query],
            "yum": ["yum", "search", query],
            "pacman": ["pacman", "-Ss", query],
            "zypper": ["zypper", "search", query],
            "brew": ["brew", "search", query],
            "apk": ["apk", "search", query],
            "winget": ["winget", "search", query],
            "choco": ["choco", "search", query],
        }
        cmd = cmd_map.get(m)
        if cmd is None:
            return {"error": f"Менеджер {m} не поддерживается"}
        return self._run(cmd, timeout=120)

    def list_installed(self, manager: str = "auto") -> dict[str, Any]:
        """Список установленных пакетов."""
        m = self._resolve_manager(manager)
        cmd_map = {
            "apt": ["dpkg", "--get-selections"],
            "apt-get": ["dpkg", "--get-selections"],
            "dnf": ["dnf", "list", "installed"],
            "yum": ["yum", "list", "installed"],
            "pacman": ["pacman", "-Q"],
            "zypper": ["zypper", "search", "-i"],
            "brew": ["brew", "list"],
            "apk": ["apk", "info"],
            "winget": ["winget", "list"],
            "choco": ["choco", "list", "--local-only"],
        }
        cmd = cmd_map.get(m)
        if cmd is None:
            return {"error": f"Менеджер {m} не поддерживается"}
        return self._run(cmd, timeout=120)

    def pip_install(self, package: str, user: bool = True) -> dict[str, Any]:
        """Установка Python-пакета через pip."""
        if not shutil.which("pip") and not shutil.which("pip3"):
            return {"error": "pip не найден"}
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        cmd = [pip_cmd, "install", package]
        if user:
            cmd.insert(2, "--user")
        return self._run(cmd, timeout=600)

    def npm_install(
        self, package: str, global_: bool = False, cwd: str = ""
    ) -> dict[str, Any]:
        """Установка npm-пакета."""
        if not shutil.which("npm"):
            return {"error": "npm не найден"}
        cmd = ["npm", "install"]
        if global_:
            cmd.append("-g")
        cmd.append(package)
        cwd = os.path.expanduser(cwd) if cwd else None
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=900, cwd=cwd
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-4000:],
            }
        except Exception as e:
            return {"error": f"npm_install error: {e}"}
