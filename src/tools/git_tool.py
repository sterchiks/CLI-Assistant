"""Git-операции через subprocess (без внешних зависимостей)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class GitTool:
    """Обёртка над git CLI."""

    def _git(self, args: list[str], cwd: str = ".", timeout: int = 120) -> dict[str, Any]:
        if not shutil.which("git"):
            return {"error": "git не установлен"}
        try:
            cwd = os.path.expanduser(cwd)
            proc = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"git {' '.join(args)}: таймаут"}
        except Exception as e:
            return {"error": f"git error: {e}"}

    def git_status(self, cwd: str = ".") -> dict[str, Any]:
        """git status (короткий вывод)."""
        r = self._git(["status", "--short", "--branch"], cwd=cwd)
        if r.get("success"):
            lines = r["stdout"].splitlines()
            branch_line = lines[0] if lines and lines[0].startswith("##") else ""
            files = lines[1:] if branch_line else lines
            return {
                "branch_info": branch_line,
                "files": files,
                "clean": len(files) == 0,
            }
        return r

    def git_log(self, cwd: str = ".", limit: int = 10) -> dict[str, Any]:
        """История коммитов."""
        fmt = "%H|%an|%ae|%ad|%s"
        r = self._git(
            ["log", f"-{int(limit)}", f"--pretty=format:{fmt}", "--date=iso"],
            cwd=cwd,
        )
        if not r.get("success"):
            return r
        commits = []
        for line in r["stdout"].splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })
        return {"commits": commits, "count": len(commits)}

    def git_commit(
        self, message: str, add_all: bool = True, cwd: str = "."
    ) -> dict[str, Any]:
        """git add + commit."""
        if add_all:
            r1 = self._git(["add", "-A"], cwd=cwd)
            if not r1.get("success"):
                return r1
        return self._git(["commit", "-m", message], cwd=cwd)

    def git_push(
        self, remote: str = "origin", branch: str = "", cwd: str = "."
    ) -> dict[str, Any]:
        """git push."""
        args = ["push", remote]
        if branch:
            args.append(branch)
        return self._git(args, cwd=cwd, timeout=300)

    def git_pull(self, remote: str = "origin", cwd: str = ".") -> dict[str, Any]:
        """git pull."""
        return self._git(["pull", remote], cwd=cwd, timeout=300)

    def git_clone(self, url: str, destination: str = "") -> dict[str, Any]:
        """git clone."""
        args = ["clone", url]
        if destination:
            args.append(os.path.expanduser(destination))
        return self._git(args, cwd=".", timeout=600)

    def git_branch(self, cwd: str = ".") -> dict[str, Any]:
        """Список веток + текущая."""
        r = self._git(["branch", "--list"], cwd=cwd)
        if not r.get("success"):
            return r
        branches = []
        current = ""
        for line in r["stdout"].splitlines():
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("*"):
                name = line[1:].strip()
                current = name
                branches.append(name)
            else:
                branches.append(line.strip())
        return {"current": current, "branches": branches}

    def git_checkout(
        self, branch: str, create: bool = False, cwd: str = "."
    ) -> dict[str, Any]:
        """git checkout (с -b при create=True)."""
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        return self._git(args, cwd=cwd)

    def git_diff(self, cwd: str = ".") -> dict[str, Any]:
        """git diff (несохранённые изменения)."""
        return self._git(["diff", "--no-color"], cwd=cwd, timeout=60)
