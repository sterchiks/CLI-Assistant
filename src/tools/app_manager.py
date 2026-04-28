"""Менеджер приложений: открытие/закрытие/переключение рабочих столов."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore


# Алиасы / эвристики поиска приложений
_APP_ALIASES: dict[str, list[str]] = {
    "firefox": ["firefox", "firefox-esr", "firefox-bin"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "chromium": ["chromium", "chromium-browser"],
    "browser": ["firefox", "google-chrome", "chromium", "chromium-browser", "brave-browser"],
    "terminal": ["gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "xterm", "tilix"],
    "terminal_emulator": ["gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"],
    "файловый_менеджер": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
    "files": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
    "code": ["code", "code-insiders", "codium"],
    "vscode": ["code", "code-insiders", "codium"],
    "editor": ["code", "subl", "gedit", "kate", "nano"],
    "telegram": ["telegram-desktop", "Telegram"],
}


def _resolve_executable(app_name: str) -> Optional[str]:
    key = app_name.strip().lower().replace(" ", "_")
    candidates = _APP_ALIASES.get(key, [])
    if not candidates:
        candidates = [app_name]
    for c in candidates:
        path = shutil.which(c)
        if path:
            return path
    return None


class AppManager:
    """Открытие/закрытие приложений и управление рабочими столами."""

    # ---------- helpers ----------

    @staticmethod
    def _has(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    @staticmethod
    def _detect_de() -> str:
        de = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
        if "gnome" in de:
            return "gnome"
        if "kde" in de or "plasma" in de:
            return "kde"
        if "xfce" in de:
            return "xfce"
        return de or "unknown"

    @staticmethod
    def _run(cmd: list[str], timeout: int = 10) -> dict[str, Any]:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as e:
            return {"error": f"{cmd[0]}: {e}"}

    # ---------- workspaces ----------

    def switch_workspace(self, workspace: int) -> dict[str, Any]:
        """Переключиться на рабочий стол (1-based)."""
        ws = max(1, int(workspace))
        idx = ws - 1
        de = self._detect_de()
        # KDE
        if de == "kde" and self._has("qdbus"):
            r = self._run(["qdbus", "org.kde.KWin", "/KWin", "setCurrentDesktop", str(ws)])
            if r.get("success"):
                return {"success": True, "workspace": ws, "method": "qdbus"}
        # wmctrl
        if self._has("wmctrl"):
            r = self._run(["wmctrl", "-s", str(idx)])
            if r.get("success"):
                return {"success": True, "workspace": ws, "method": "wmctrl"}
        # xdotool
        if self._has("xdotool"):
            r = self._run(["xdotool", "set_desktop", str(idx)])
            if r.get("success"):
                return {"success": True, "workspace": ws, "method": "xdotool"}
        return {
            "error": "Не удалось переключить рабочий стол. Установи wmctrl или xdotool.",
            "desktop_environment": de,
        }

    def move_window_to_workspace(
        self, window_title: str, workspace: int
    ) -> dict[str, Any]:
        """Переместить окно (по подстроке заголовка) на другой рабочий стол."""
        if not self._has("wmctrl"):
            return {"error": "wmctrl не установлен"}
        idx = max(1, int(workspace)) - 1
        r = self._run(["wmctrl", "-r", window_title, "-t", str(idx)])
        if r.get("success"):
            return {"success": True, "window": window_title, "workspace": int(workspace)}
        return {"error": r.get("stderr") or "Не удалось переместить окно"}

    # ---------- list windows ----------

    def list_open_applications(self) -> list[dict[str, Any]]:
        """Список открытых GUI-окон."""
        if self._has("wmctrl"):
            r = self._run(["wmctrl", "-lp"])
            if r.get("success"):
                items = []
                for line in r["stdout"].splitlines():
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        try:
                            ws = int(parts[1])
                            pid = int(parts[2])
                        except ValueError:
                            continue
                        # parts[3] — host, parts[4] — title
                        title = parts[4]
                        name = ""
                        if psutil is not None:
                            try:
                                name = psutil.Process(pid).name()
                            except Exception:
                                pass
                        items.append({
                            "window_id": parts[0],
                            "workspace": ws + 1 if ws >= 0 else 0,
                            "pid": pid,
                            "name": name,
                            "title": title,
                        })
                return items
        if self._has("xdotool"):
            r = self._run(["xdotool", "search", "--name", ".+"])
            if r.get("success"):
                return [{"window_id": wid} for wid in r["stdout"].splitlines() if wid]
        return [{"error": "Установи wmctrl или xdotool для управления окнами"}]

    # ---------- open ----------

    def open_application(
        self,
        app_name: str,
        workspace: int = 1,
        args: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Открыть приложение (опционально на конкретном рабочем столе)."""
        args = args or []
        exe = _resolve_executable(app_name)
        if exe is None:
            # Пробуем через xdg-open / start / open
            system = platform.system().lower()
            try:
                if system == "linux" and self._has("xdg-open"):
                    proc = subprocess.Popen(
                        ["xdg-open", app_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return {
                        "success": True,
                        "pid": proc.pid,
                        "app": app_name,
                        "method": "xdg-open",
                        "workspace": workspace,
                    }
                if system == "darwin":
                    proc = subprocess.Popen(
                        ["open", "-a", app_name, *args],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return {"success": True, "pid": proc.pid, "app": app_name, "method": "open"}
                if system == "windows":
                    proc = subprocess.Popen(
                        ["cmd", "/c", "start", "", app_name, *args],
                        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                    )
                    return {"success": True, "pid": proc.pid, "app": app_name, "method": "start"}
            except Exception as e:
                return {"error": f"Не удалось запустить {app_name}: {e}"}
            return {"error": f"Приложение не найдено: {app_name}"}

        try:
            proc = subprocess.Popen(
                [exe, *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            return {"error": f"Popen error: {e}"}

        # Переключение/перенос на нужный рабочий стол
        moved = False
        if int(workspace) >= 1 and (self._has("wmctrl") or self._has("xdotool")):
            time.sleep(0.7)
            # Сначала переключимся на нужный desktop, чтобы окно «прилипло»
            self.switch_workspace(int(workspace))
            moved = True

        return {
            "success": True,
            "pid": proc.pid,
            "app": os.path.basename(exe),
            "executable": exe,
            "workspace": int(workspace),
            "moved_to_workspace": moved,
        }

    # ---------- close ----------

    def close_application(self, identifier: str) -> dict[str, Any]:
        """Закрыть приложение по имени или PID."""
        killed_pids: list[int] = []
        method = ""

        # Если это число — трактуем как PID
        try:
            pid = int(str(identifier).strip())
            if psutil is None:
                return {"error": "psutil не установлен"}
            try:
                p = psutil.Process(pid)
                p.terminate()
                method = "SIGTERM"
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                    method = "SIGKILL"
                killed_pids.append(pid)
                return {"success": True, "killed_pids": killed_pids, "method": method}
            except psutil.NoSuchProcess:
                return {"error": f"PID {pid} не найден"}
            except psutil.AccessDenied:
                return {"error": f"Нет доступа к PID {pid}"}
        except ValueError:
            pass

        # Поиск по имени
        needle = identifier.lower()
        if psutil is not None:
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (p.info.get("name") or "").lower()
                    cmdline = " ".join(p.info.get("cmdline") or []).lower()
                    if needle == name or needle in name or needle in cmdline:
                        try:
                            p.terminate()
                            killed_pids.append(p.info["pid"])
                        except Exception:
                            continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if killed_pids:
            method = "SIGTERM (psutil)"
            time.sleep(3)
            # Дожимаем оставшихся
            for pid in list(killed_pids):
                try:
                    p = psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                        method = "SIGKILL (psutil)"
                except Exception:
                    pass
            return {"success": True, "killed_pids": killed_pids, "method": method}

        # Fallback на wmctrl -c (закрытие окна по заголовку)
        if self._has("wmctrl"):
            r = self._run(["wmctrl", "-c", identifier])
            if r.get("success"):
                return {
                    "success": True,
                    "killed_pids": [],
                    "method": "wmctrl -c (window close)",
                }

        return {"error": f"Не найдено процессов или окон: {identifier}"}
