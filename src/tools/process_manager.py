"""Менеджер процессов на базе psutil."""

from __future__ import annotations

import logging
import signal
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore


class ProcessManager:
    """Управление процессами через psutil."""

    def list_processes(self, sort_by: str = "cpu", limit: int = 20) -> list[dict[str, Any]]:
        """Список процессов. sort_by: cpu/memory/name/pid."""
        if psutil is None:
            return [{"error": "psutil не установлен"}]
        try:
            # Прайминг cpu_percent
            for p in psutil.process_iter():
                try:
                    p.cpu_percent(None)
                except Exception:
                    pass
            time.sleep(0.2)

            procs: list[dict[str, Any]] = []
            for p in psutil.process_iter(["pid", "name", "username", "status"]):
                try:
                    info = p.info
                    cpu = p.cpu_percent(None)
                    mem = p.memory_info().rss
                    procs.append({
                        "pid": info["pid"],
                        "name": info.get("name") or "",
                        "user": info.get("username") or "",
                        "status": info.get("status") or "",
                        "cpu_percent": round(cpu, 1),
                        "memory_mb": round(mem / (1024 * 1024), 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception:
                    continue

            key_map = {
                "cpu": lambda x: x["cpu_percent"],
                "memory": lambda x: x["memory_mb"],
                "name": lambda x: x["name"].lower(),
                "pid": lambda x: x["pid"],
            }
            key_fn = key_map.get(sort_by, key_map["cpu"])
            reverse = sort_by in ("cpu", "memory")
            procs.sort(key=key_fn, reverse=reverse)
            return procs[: max(1, int(limit))]
        except Exception as e:
            return [{"error": f"list_processes error: {e}"}]

    def kill_process(self, pid: int, force: bool = False) -> dict[str, Any]:
        """Завершить процесс. force=True использует SIGKILL."""
        if psutil is None:
            return {"error": "psutil не установлен"}
        try:
            p = psutil.Process(int(pid))
            name = p.name()
            if force:
                p.kill()
                method = "SIGKILL"
            else:
                p.terminate()
                method = "SIGTERM"
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                    method = "SIGKILL (after SIGTERM timeout)"
            return {"success": True, "pid": int(pid), "name": name, "method": method}
        except psutil.NoSuchProcess:
            return {"error": f"Процесс с PID {pid} не найден"}
        except psutil.AccessDenied:
            return {"error": f"Нет доступа к процессу {pid} (нужен sudo)"}
        except Exception as e:
            return {"error": f"kill_process error: {e}"}

    def find_process(self, name: str) -> list[dict[str, Any]]:
        """Поиск процессов по подстроке имени."""
        if psutil is None:
            return [{"error": "psutil не установлен"}]
        try:
            needle = name.lower()
            results = []
            for p in psutil.process_iter(["pid", "name", "username", "cmdline"]):
                try:
                    info = p.info
                    pname = (info.get("name") or "").lower()
                    cmdline = " ".join(info.get("cmdline") or []).lower()
                    if needle in pname or needle in cmdline:
                        results.append({
                            "pid": info["pid"],
                            "name": info.get("name"),
                            "user": info.get("username"),
                            "cmdline": " ".join(info.get("cmdline") or [])[:200],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return results
        except Exception as e:
            return [{"error": f"find_process error: {e}"}]

    def get_process_info(self, pid: int) -> dict[str, Any]:
        """Детальная информация о процессе."""
        if psutil is None:
            return {"error": "psutil не установлен"}
        try:
            p = psutil.Process(int(pid))
            with p.oneshot():
                info: dict[str, Any] = {
                    "pid": p.pid,
                    "name": p.name(),
                    "status": p.status(),
                    "user": p.username(),
                    "exe": _safe(lambda: p.exe()),
                    "cwd": _safe(lambda: p.cwd()),
                    "cmdline": _safe(lambda: " ".join(p.cmdline())),
                    "create_time": p.create_time(),
                    "cpu_percent": p.cpu_percent(0.1),
                    "memory_mb": round(p.memory_info().rss / (1024 * 1024), 2),
                    "num_threads": p.num_threads(),
                    "ppid": p.ppid(),
                    "children": [c.pid for c in _safe_iter(p.children)],
                    "open_files": [f.path for f in _safe_iter(p.open_files)][:50],
                    "connections": [
                        {
                            "fd": getattr(c, "fd", None),
                            "family": str(c.family),
                            "type": str(c.type),
                            "laddr": str(c.laddr) if c.laddr else "",
                            "raddr": str(c.raddr) if c.raddr else "",
                            "status": c.status,
                        }
                        for c in _safe_iter(p.connections)
                    ][:50],
                }
            return info
        except psutil.NoSuchProcess:
            return {"error": f"Процесс PID {pid} не найден"}
        except psutil.AccessDenied:
            return {"error": f"Нет доступа к процессу {pid}"}
        except Exception as e:
            return {"error": f"get_process_info error: {e}"}

    def get_top_processes(self, limit: int = 5) -> list[dict[str, Any]]:
        """Топ процессов по потреблению памяти."""
        if psutil is None:
            return [{"error": "psutil не установлен"}]
        try:
            procs = []
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    mem = p.memory_info().rss
                    procs.append({
                        "pid": p.info["pid"],
                        "name": p.info.get("name") or "",
                        "memory_bytes": mem,
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            procs.sort(key=lambda x: x["memory_bytes"], reverse=True)
            top = procs[: max(1, int(limit))]
            for item in top:
                mb = item["memory_bytes"] / (1024 * 1024)
                if mb >= 1024:
                    item["memory_gb"] = round(mb / 1024, 2)
                    item["display"] = f"{item['memory_gb']} ГБ"
                else:
                    item["memory_mb"] = round(mb, 1)
                    item["display"] = f"{item['memory_mb']} МБ"
                item.pop("memory_bytes", None)
            return top
        except Exception as e:
            return [{"error": f"get_top_processes error: {e}"}]


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _safe_iter(fn):
    try:
        return fn() or []
    except Exception:
        return []
