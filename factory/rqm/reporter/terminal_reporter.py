from __future__ import annotations

from factory.rqm.model.quality_report import QualityReport


class TerminalReporter:
    """
    Render a Release Quality Manager report to the terminal.
    """

    ARROWS = {
        "UP": "↑",
        "DOWN": "↓",
        "STABLE": "→",
        "NEW": "•",
    }

    def render(self, report: QualityReport) -> None:
        """Render the report."""
        arrow = self.ARROWS.get(report.trend, "•")

        print("═" * 64)
        print(f" QUALITY SCORE     {report.overall_score:.1f}/100")
        print(f" TREND             {arrow} {report.trend} ({report.delta:+.1f})")
        print(f" DECISION          {report.decision.value}")
        print("═" * 64)

        for result in report.providers:
            status = "PASS" if result.passed else "FAIL"
            print(
                f" {result.name:<24}"
                f"{status:<10}"
                f"findings={len(result.findings):<3}"
                f" time={result.duration:.2f}s"
            )

        print("═" * 64)
        print()
