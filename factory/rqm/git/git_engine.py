from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GitStatus:
    branch: Optional[str]
    commit: Optional[str]
    dirty: bool


class GitEngine:
    """
    Minimal Git adapter used by RQM.
    """

    def __init__(self, root: Path):
        self.root = root

    def get_status(self) -> GitStatus:
        return GitStatus(
            branch=self._branch(),
            commit=self._commit(),
            dirty=self._dirty(),
        )

    def _branch(self) -> Optional[str]:
        return self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        )

    def _commit(self) -> Optional[str]:
        return self._run(
            ["git", "rev-parse", "--short", "HEAD"]
        )

    def _dirty(self) -> bool:
        status = self._run(
            ["git", "status", "--porcelain"]
        )

        if status is None:
            return False

        return bool(status.strip())

    def _run(
        self,
        command: list[str],
    ) -> Optional[str]:
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode != 0:
                return None

            return result.stdout.strip()

        except Exception:
            return None