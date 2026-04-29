"""Менеджер systemd-сервисов через systemctl/journalctl."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ServiceManager:
    """Управление systemd-сервисами. Большинство операций требуют sudo."""

    def _has_systemctl(self) -> bool:
        return shutil.which("systemctl") is not None

    def _run(self, cmd: list[str], timeout: int = 60) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Таймаут: {' '.join(cmd)}"}
        except Exception as e:
            return {"error": f"_run error: {e}"}

    def list_services(self, status_filter: str = "all") -> dict[str, Any]:
        """Список сервисов. status_filter: all/running/failed/inactive."""
        if not self._has_systemctl():
            return {"error": "systemctl недоступен (не systemd-система)"}
        args = ["systemctl", "list-units", "--type=service", "--no-pager", "--plain"]
        if status_filter == "running":
            args.append("--state=running")
        elif status_filter == "failed":
            args.append("--state=failed")
        elif status_filter == "inactive":
            args.append("--state=inactive")
        else:
            args.append("--all")
        r = self._run(args, timeout=30)
        if not r.get("success"):
            return r

        services = []
        for line in r["stdout"].splitlines():
            line = line.strip()
            if not line or line.startswith(("UNIT", "LOAD", "●")) or "loaded units listed" in line.lower():
                continue
            parts = line.split(None, 4)
            if len(parts) >= 4 and parts[0].endswith(".service"):
                services.append({
                    "unit": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": parts[4] if len(parts) > 4 else "",
                })
        return {"count": len(services), "services": services}

    def service_status(self, name: str) -> dict[str, Any]:
        """Статус сервиса + логи последних строк."""
        if not self._has_systemctl():
            return {"error": "systemctl недоступен"}
        r = self._run(
            ["systemctl", "status", name, "--no-pager", "-n", "20"], timeout=20
        )
        is_active = self._run(["systemctl", "is-active", name], timeout=10)
        is_enabled = self._run(["systemctl", "is-enabled", name], timeout=10)
        return {
            "name": name,
            "is_active": (is_active.get("stdout") or "").strip(),
            "is_enabled": (is_enabled.get("stdout") or "").strip(),
            "status_output": r.get("stdout", ""),
            "stderr": r.get("stderr", ""),
        }

    def _service_action(self, action: str, name: str) -> dict[str, Any]:
        if not self._has_systemctl():
            return {"error": "systemctl недоступен"}
        return {
            "requires_sudo": True,
            "command": f"systemctl {action} {name}",
            "message": f"Действие {action} для {name} требует sudo. Используй run_as_root.",
        }

    def start_service(self, name: str) -> dict[str, Any]:
        return self._service_action("start", name)

    def stop_service(self, name: str) -> dict[str, Any]:
        return self._service_action("stop", name)

    def restart_service(self, name: str) -> dict[str, Any]:
        return self._service_action("restart", name)

    def enable_service(self, name: str) -> dict[str, Any]:
        return self._service_action("enable", name)

    def disable_service(self, name: str) -> dict[str, Any]:
        return self._service_action("disable", name)

    def get_service_logs(self, name: str, lines: int = 50) -> dict[str, Any]:
        """Логи сервиса через journalctl."""
        if not shutil.which("journalctl"):
            return {"error": "journalctl недоступен"}
        r = self._run(
            ["journalctl", "-u", name, "-n", str(int(lines)), "--no-pager"],
            timeout=30,
        )
        if not r.get("success"):
            return r
        return {"name": name, "lines": int(lines), "logs": r["stdout"]}
