"""Управление crontab пользователя."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


_HUMAN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*every\s+minute\s*$", re.I), "* * * * *"),
    (re.compile(r"^\s*every\s+(\d+)\s*minutes?\s*$", re.I), "*/{0} * * * *"),
    (re.compile(r"^\s*every\s+hour\s*$", re.I), "0 * * * *"),
    (re.compile(r"^\s*every\s+(\d+)\s*hours?\s*$", re.I), "0 */{0} * * *"),
    (re.compile(r"^\s*hourly\s*$", re.I), "0 * * * *"),
    (re.compile(r"^\s*daily\s*$", re.I), "0 0 * * *"),
    (re.compile(r"^\s*weekly\s*$", re.I), "0 0 * * 0"),
    (re.compile(r"^\s*monthly\s*$", re.I), "0 0 1 * *"),
    (re.compile(r"^\s*yearly\s*$", re.I), "0 0 1 1 *"),
    (re.compile(r"^\s*every\s+day\s+at\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\s*$", re.I), None),  # type: ignore
]


def parse_human_schedule(text: str) -> str:
    """Конвертирует человеческий формат в cron-строку."""
    txt = text.strip()
    # Если уже похоже на cron (5 полей)
    if len(txt.split()) == 5:
        return txt

    for pat, fmt in _HUMAN_PATTERNS:
        m = pat.match(txt)
        if not m:
            continue
        if fmt is None:
            # "every day at HH[:MM] [am/pm]"
            hh = int(m.group(1))
            mm = int(m.group(2) or 0)
            ampm = (m.group(3) or "").lower()
            if ampm == "pm" and hh < 12:
                hh += 12
            if ampm == "am" and hh == 12:
                hh = 0
            return f"{mm} {hh} * * *"
        if "{0}" in fmt:
            return fmt.format(m.group(1))
        return fmt
    raise ValueError(f"Не удалось распознать расписание: {text}")


class CronTool:
    """Работа с crontab текущего пользователя."""

    def _has_crontab(self) -> bool:
        return shutil.which("crontab") is not None

    def _read_crontab(self) -> list[str]:
        if not self._has_crontab():
            return []
        try:
            proc = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                return []
            return proc.stdout.splitlines()
        except Exception:
            return []

    def _write_crontab(self, lines: list[str]) -> dict[str, Any]:
        if not self._has_crontab():
            return {"error": "crontab не установлен"}
        content = "\n".join(lines)
        if not content.endswith("\n"):
            content += "\n"
        try:
            proc = subprocess.run(
                ["crontab", "-"],
                input=content,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "success": proc.returncode == 0,
                "stderr": proc.stderr,
            }
        except Exception as e:
            return {"error": f"_write_crontab error: {e}"}

    def list_crons(self, user: str = "current") -> dict[str, Any]:
        """Список cron-заданий текущего пользователя."""
        if not self._has_crontab():
            return {"error": "crontab не установлен"}
        lines = self._read_crontab()
        items = []
        idx = 0
        for raw in lines:
            line = raw.rstrip()
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                items.append({"index": idx, "comment": line.lstrip("#").strip(), "raw": line})
                idx += 1
                continue
            parts = line.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command = parts[5]
                items.append({
                    "index": idx,
                    "schedule": schedule,
                    "command": command,
                    "raw": line,
                })
            else:
                items.append({"index": idx, "raw": line})
            idx += 1
        return {"count": len(items), "entries": items}

    def add_cron(
        self, schedule: str, command: str, comment: str = ""
    ) -> dict[str, Any]:
        """Добавить cron-задание (поддерживается человеческий формат)."""
        if not self._has_crontab():
            return {"error": "crontab не установлен"}
        try:
            cron_schedule = parse_human_schedule(schedule)
        except ValueError as e:
            return {"error": str(e)}

        lines = self._read_crontab()
        if comment:
            lines.append(f"# {comment}")
        lines.append(f"{cron_schedule} {command}")
        r = self._write_crontab(lines)
        if r.get("success"):
            return {"success": True, "schedule": cron_schedule, "command": command}
        return r

    def remove_cron(self, index: int) -> dict[str, Any]:
        """Удалить cron-задание по индексу из list_crons()."""
        lines = self._read_crontab()
        # Воссоздаём ту же индексацию что и в list_crons
        keep: list[str] = []
        idx = 0
        removed = False
        for raw in lines:
            line = raw.rstrip()
            if not line.strip():
                keep.append(raw)
                continue
            if idx == int(index):
                removed = True
            else:
                keep.append(raw)
            idx += 1
        if not removed:
            return {"error": f"Нет записи с индексом {index}"}
        r = self._write_crontab(keep)
        if r.get("success"):
            return {"success": True, "removed_index": int(index)}
        return r

    def edit_cron(
        self, index: int, schedule: str = "", command: str = ""
    ) -> dict[str, Any]:
        """Изменить расписание/команду cron-задания."""
        lines = self._read_crontab()
        idx = 0
        edited = False
        for i, raw in enumerate(lines):
            line = raw.rstrip()
            if not line.strip():
                continue
            if idx == int(index):
                if line.lstrip().startswith("#"):
                    return {"error": "По указанному индексу — комментарий, а не задание"}
                parts = line.split(None, 5)
                if len(parts) < 6:
                    return {"error": "Запись имеет неожиданный формат"}
                old_schedule = " ".join(parts[:5])
                old_command = parts[5]
                new_schedule = old_schedule
                new_command = old_command
                if schedule:
                    try:
                        new_schedule = parse_human_schedule(schedule)
                    except ValueError as e:
                        return {"error": str(e)}
                if command:
                    new_command = command
                lines[i] = f"{new_schedule} {new_command}"
                edited = True
                break
            idx += 1
        if not edited:
            return {"error": f"Нет записи с индексом {index}"}
        return self._write_crontab(lines)
