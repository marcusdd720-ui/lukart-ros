"""
RQM 3.0 Foundation – Orchestrator
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from factory.rqm.model.quality_report import QualityReport
from factory.rqm.model.release_decision import ReleaseDecision
from factory.rqm.model.provider_result import ProviderResult
from factory.rqm.providers.pytest_provider import PytestProvider
from factory.rqm.providers.audit_provider import AuditProvider


class RQMCore:
    def __init__(self, root: Optional[Path] = None):
        self.root = (root or Path.cwd()).resolve()
        self.history_file = self.root / "rqm_history.json"

    def run(self) -> QualityReport:
        print("🚀 RQM 3.0 Foundation – Running quality analysis...\n")

        providers = [
            PytestProvider(self.root),
            AuditProvider(self.root),
        ]

        results: List[ProviderResult] = [p.run() for p in providers]
        score = self._score(results)
        decision = self._decide(score, results)
        trend, delta = self._trend(score)

        report = QualityReport(
            version="3.0",
            timestamp=datetime.now(),
            overall_score=score,
            decision=decision,
            providers=results,
            trend=trend,
            delta=delta,
            metadata={"root": str(self.root)},
        )

        self._save_history(report)
        self._print(report)
        return report

    def _score(self, results: List[ProviderResult]) -> float:
        score = 100.0
        for r in results:
            if r.provider == "pytest":
                failed = int(r.metrics.get("failed", 0))
                if failed > 0:
                    score -= 40
                    score -= failed * 2
            elif r.provider == "code_audit":
                score -= int(r.metrics.get("errors", 0)) * 8
                score -= int(r.metrics.get("warnings", 0)) * 2
        return round(max(0.0, min(100.0, score)), 2)

    def _decide(self, score: float, results: List[ProviderResult]) -> ReleaseDecision:
        has_error = any(
            f.severity == "ERROR"
            for r in results
            for f in r.findings
        )
        if has_error or score < 85:
            return ReleaseDecision.BLOCKED
        if score < 95:
            return ReleaseDecision.MANUAL_REVIEW
        return ReleaseDecision.READY_FOR_MERGE

    def _trend(self, score: float) -> tuple[str, float]:
        history = self._load_history()
        if not history:
            return "NEW", 0.0
        prev = float(history[-1].get("overall_score", score))
        delta = round(score - prev, 2)
        if delta >= 1:
            return "UP", delta
        if delta <= -1:
            return "DOWN", delta
        return "STABLE", delta

    def _load_history(self) -> list:
        if not self.history_file.exists():
            return []
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_history(self, report: QualityReport) -> None:
        history = self._load_history()
        history.append(
            {
                "timestamp": report.timestamp.isoformat(),
                "overall_score": report.overall_score,
                "decision": report.decision.value,
                "trend": report.trend,
                "delta": report.delta,
            }
        )
        self.history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def _print(self, report: QualityReport) -> None:
        arrow = {"UP": "↑", "DOWN": "↓", "STABLE": "→", "NEW": "•"}.get(report.trend, "•")
        print("═" * 64)
        print(f" QUALITY SCORE     {report.overall_score:.1f}/100")
        print(f" TREND             {arrow} {report.trend} ({report.delta:+.1f})")
        print(f" DECISION          {report.decision.value}")
        print("═" * 64)
        for p in report.providers:
            print(f" {p.provider:<12} {p.status.value:<8}  findings={len(p.findings)}  time={p.duration:.2f}s")
        print("═" * 64)
        print()


if __name__ == "__main__":
    report = RQMCore().run()
    if report.decision.value == "BLOCKED":
        raise SystemExit(1)