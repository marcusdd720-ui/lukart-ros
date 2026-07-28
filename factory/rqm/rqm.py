from __future__ import annotations

from pathlib import Path

from factory.rqm.git.git_engine import GitEngine
from factory.rqm.quality.quality_engine import QualityEngine
from factory.rqm.reporter.reporter import ReportGenerator
from factory.rqm.state.state import StateManager


class ReleaseQualityManager:
    """
    High-level facade for the Release Quality Manager.
    """

    def __init__(self, root: Path):
        self.root = root

        self.quality_engine = QualityEngine(root)
        self.report_generator = ReportGenerator()
        self.state = StateManager(root)
        self.git = GitEngine(root)

    def run(self):

        report = self.quality_engine.run()

        git_status = self.git.get_status()

        report.metadata["git"] = {
            "branch": git_status.branch,
            "commit": git_status.commit,
            "dirty": git_status.dirty,
        }

        self.state.save_snapshot(report)

        report_path = self.root / "reports" / "quality_report.md"

        self.report_generator.save_markdown(
            report,
            report_path,
        )

        return report


def main() -> int:

    root = Path.cwd()

    manager = ReleaseQualityManager(root)

    report = manager.run()

    print()
    print("=" * 60)
    print("Release Quality Manager")
    print("=" * 60)
    print(f"Score    : {report.overall_score:.1f}")
    print(f"Decision : {report.decision.value}")
    print(f"Providers: {len(report.providers)}")
    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
