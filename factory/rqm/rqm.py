"""
Release & Quality Manager (RQM) v3.1
Enterprise-grade tool for repository intelligence and release management.
"""

import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from factory.rqm.core.event_bus import EventBus
from factory.rqm.core.score_engine import ScoreEngine
from factory.rqm.core.release_decision import ReleaseDecision
from factory.rqm.scanner.scanner import ProjectScanner
from factory.rqm.state.state import StateManager
from factory.rqm.git.git_engine import GitEngine
from factory.rqm.quality.quality_engine import QualityEngine
from factory.rqm.reporter.reporter import ReportGenerator


@dataclass
class ProjectHealth:
    score: float
    status: str
    decision: ReleaseDecision
    pass_count: int
    active_count: int
    fix_count: int
    failed_tests: int
    summary: str
    timestamp: datetime
    duration: float


class ReleaseQualityManager:
    """RQM v3.1 — Modular, extensible, production-ready."""

    def __init__(self, project_root: Path):
        self.root = project_root.absolute()
        self.event_bus = EventBus()
        self.scanner = ProjectScanner(self.root)
        self.state = StateManager(self.root)
        self.git = GitEngine(self.root)
        self.quality = QualityEngine(self.root)
        self.score_engine = ScoreEngine()
        self.reporter = ReportGenerator(self.root)

        self._register_events()

    def _register_events(self):
        """Event-driven architecture."""
        self.event_bus.subscribe("scan_complete", self.state.on_scan_complete)
        self.event_bus.subscribe("quality_complete", self.score_engine.on_quality_complete)

    def run(self, verbose: bool = True) -> ProjectHealth:
        start = datetime.now()

        if verbose:
            print("🚀 RQM v3.1 — Galaxy Class Repository Intelligence\n")

        git_status = self.git.get_status()
        files = self.scanner.scan()
        self.event_bus.emit("scan_complete", files)

        changes = self.state.analyze_changes(files)
        quality_report = self.quality.run_all_checks()
        self.event_bus.emit("quality_complete", quality_report)

        health = self._calculate_health(quality_report, changes, git_status, start)

        self.state.save_state(files, changes, health)
        self.reporter.generate_full_report(health, quality_report, changes, git_status)

        if verbose:
            self._print_dashboard(health)

        return health

    def _calculate_health(self, quality, changes, git_status, start) -> ProjectHealth:
        score = self.score_engine.calculate(quality, changes, git_status)
        decision = ReleaseDecision.from_score(score, quality)

        return ProjectHealth(
            score=score,
            status=decision.value,
            decision=decision,
            pass_count=len([c for c in changes if c.get("status") == "LOCKED"]),
            active_count=len([c for c in changes if c.get("status") == "ACTIVE"]),
            fix_count=len([c for c in changes if c.get("status") == "FIX"]),
            failed_tests=quality.get("failed_tests", 0),
            summary=decision.summary,
            timestamp=datetime.now(),
            duration=(datetime.now() - start).total_seconds()
        )

    def _print_dashboard(self, health: ProjectHealth):
        print(f"\n{'═' * 70}")
        print(f" RQM v3.1 — REPOSITORY HEALTH: {health.score:.2f}% ")
        print(f"{'═' * 70}")
        print(f"PASS ............. {health.pass_count}")
        print(f"ACTIVE ........... {health.active_count}")
        print(f"FIX .............. {health.fix_count}")
        print(f"FAILED TESTS ..... {health.failed_tests}")
        print(f"\nSTATUS: {health.summary}")
        print(f"RELEASE DECISION: {health.decision.value}")
        print(f"{'═' * 70}\n")


def main():
    root = Path.cwd()
    rqm = ReleaseQualityManager(root)
    rqm.run()


if __name__ == "__main__":
    main()