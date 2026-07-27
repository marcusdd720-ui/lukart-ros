from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.rqm.model.quality_report import QualityReport


class StateManager:
    """
    Stores RQM execution history.
    """

    def __init__(
        self,
        root: Path,
        filename: str = "rqm_history.json",
    ) -> None:
        self.path = root / filename

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        try:
            return json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except Exception:
            return []

    def save_snapshot(
        self,
        report: QualityReport,
    ) -> None:
        history = self.load()

        history.append(
            {
                "timestamp": report.timestamp.isoformat(),
                "overall_score": report.overall_score,
                "decision": report.decision.value,
                "trend": getattr(report, "trend", "NEW"),
                "delta": getattr(report, "delta", 0.0),
            }
        )

        self.path.write_text(
            json.dumps(
                history,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def latest(self) -> dict[str, Any] | None:
        history = self.load()
        return history[-1] if history else None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()