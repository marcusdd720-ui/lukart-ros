"""
RQM 4.1 – Orchestrator
"""

from __future__ import annotations

from pathlib import Path

from factory.rqm.history.history_repository import HistoryRepository
from factory.rqm.model import Report
from factory.rqm.model.quality_report import QualityReport
from factory.rqm.provider.provider_registry import ProviderRegistry
from factory.rqm.quality.exit_policy import ExitPolicy
from factory.rqm.quality.quality_engine import QualityEngine
from factory.rqm.reporter.terminal_reporter import TerminalReporter
from factory.rqm.trend.trend_engine import TrendEngine

__all__ = ["RQMCore"]


class RQMCore:
    """Release Quality Manager orchestrator."""

    def __init__(
        self,
        root: Path | None = None,
        registry: ProviderRegistry | None = None,
        history: HistoryRepository | None = None,
        trend_engine: TrendEngine | None = None,
        reporter: TerminalReporter | None = None,
        exit_policy: ExitPolicy | None = None,
    ) -> None:
        self.root = (root or Path.cwd()).resolve()
        self.registry = registry or ProviderRegistry.default()
        self.history = history or HistoryRepository(self.root)
        self.trend_engine = trend_engine or TrendEngine()
        self.reporter = reporter or TerminalReporter()
        self.exit_policy = exit_policy or ExitPolicy()
        self.engine = QualityEngine(
            root=self.root,
            registry=self.registry,
        )

    def run(self) -> int:
        """Execute Release Quality Manager pipeline."""
        report: Report = self.engine.run()

        previous_score = self.history.last_score()
        trend = self.trend_engine.compute(report, previous_score)
        report.metadata["trend"] = trend.direction.value
        report.metadata["delta"] = trend.delta

        self.history.save(report)
        quality_report = QualityReport.from_report(report)
        self.reporter.render(quality_report)

        return self.exit_policy.exit_code(quality_report.decision)
