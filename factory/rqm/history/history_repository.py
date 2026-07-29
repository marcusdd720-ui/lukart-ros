from __future__ import annotations

import json
from pathlib import Path

from factory.rqm.model import Report


class HistoryRepository:
    """
    Stores and loads Release Quality Manager history.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[dict]:
        """
        Load history from disk.
        """
        if not self.path.exists():
            return []

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, report: Report) -> None:
        """
        Append a report summary to history.
        """
        history = self.load()

        history.append(
            {
                "score": report.score,
                "decision": report.decision.value,
                "created_at": report.created_at.isoformat(),
            }
        )

        self.path.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )

    def last_score(self) -> float | None:
        """
        Return the previous quality score.
        """
        history = self.load()

        if not history:
            return None

        return float(history[-1]["score"])