"""RQM execution history storage."""

from __future__ import annotations

import json
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
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).isoformat()

        score = getattr(report, "overall_score", None)
        if score is None:
            score = getattr(report, "score", 0.0)

        decision = getattr(report, "decision", None)
        decision_val = getattr(decision, "value", decision)
        if decision_val is None:
            decision_val = "UNKNOWN"

        history.append(
            {
                "timestamp": ts,
                "overall_score": float(score),
                "decision": str(decision_val),
                "trend": getattr(report, "trend", "NEW"),
                "delta": float(getattr(report, "delta", 0.0) or 0.0),
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