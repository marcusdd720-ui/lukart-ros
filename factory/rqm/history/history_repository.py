from __future__ import annotations

import json
from pathlib import Path

from factory.rqm.model import Report


class HistoryRepository:
    """
    Repository responsible for persisting Release Quality Manager history.
    """

    def __init__(self, history_file: Path) -> None:
        self.history_file = history_file

    def load(self) -> list[dict]:
        """
        Load history entries from disk.
        """
        if not self.history_file.exists():
            return []

        try:
            return json.loads(
                self.history_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, report: Report) -> None:
        """
        Append current report to history.
        """
        history = self.load()

        history.append(
            {
                "created_at": report.created_at.isoformat(),
                "score": report.score,
                "decision": report.decision.value,
            }
        )

        self.history_file.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )

    def last_score(self) -> float | None:
        """
        Return previous quality score.
        """
        history = self.load()

        if not history:
            return None

        return float(history[-1]["score"])