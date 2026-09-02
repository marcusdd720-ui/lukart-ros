"""RQM execution history storage."""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Any


class StateManager:
    """Stores RQM execution history."""

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
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []

    def save_snapshot(self, report: Any) -> None:
        history = self.load()

        created = getattr(report, "created_at", None) or getattr(
            report, "timestamp", None
        )
        if created is not None and hasattr(created, "isoformat"):
            ts = created.isoformat()
        else:
            from datetime import datetime

            ts = datetime.now(UTC).isoformat()

        score_raw = getattr(report, "overall_score", None)
        if score_raw is None:
            score_raw = getattr(report, "score", 0.0)
        score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.0

        decision = getattr(report, "decision", None)
        decision_val = getattr(decision, "value", decision)
        if decision_val is None:
            decision_val = "UNKNOWN"

        delta_raw = getattr(report, "delta", 0.0)
        delta = float(delta_raw) if isinstance(delta_raw, (int, float)) else 0.0

        history.append(
            {
                "timestamp": ts,
                "overall_score": score,
                "decision": str(decision_val),
                "trend": getattr(report, "trend", "NEW"),
                "delta": delta,
            }
        )

        self.path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def latest(self) -> dict[str, Any] | None:
        history = self.load()
        return history[-1] if history else None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
