from __future__ import annotations

from pathlib import Path

from factory.rqm.model import Decision, Report, Severity


class ReportGenerator:
    """
    Generates human-readable reports from the Common Domain Model.

    This class contains presentation logic only.
    No business rules should be implemented here.
    """

    def to_markdown(self, report: Report) -> str:
        """
        Generate a Markdown representation of a Report.
        """

        lines: list[str] = [
            "# RQM Quality Report",
            "",
            f"**Overall Score:** {report.score:.1f}/100",
            f"**Decision:** {report.decision.value}",
            f"**Timestamp:** {report.created_at.isoformat()}",
            f"**Providers:** {report.provider_count}",
            f"**Findings:** {report.finding_count}",
            "",
            "## Providers",
            "",
        ]

        for result in report.results:
            lines.extend(
                [
                    f"### {result.name}",
                    "",
                    f"- Status: {'PASS' if result.passed else 'FAIL'}",
                    f"- Duration: {result.duration:.2f}s",
                    f"- Findings: {result.finding_count}",
                    "",
                ]
            )

        errors = [
            finding
            for result in report.results
            for finding in result.findings
            if finding.severity == Severity.ERROR
        ]

        warnings = [
            finding
            for result in report.results
            for finding in result.findings
            if finding.severity == Severity.WARNING
        ]

        criticals = [
            finding
            for result in report.results
            for finding in result.findings
            if finding.severity == Severity.CRITICAL
        ]

        infos = [
            finding
            for result in report.results
            for finding in result.findings
            if finding.severity == Severity.INFO
        ]

        if criticals:
            lines.extend(["## Critical", ""])

            for finding in criticals:
                lines.append(self._format_finding(finding))

            lines.append("")

        if errors:
            lines.extend(["## Errors", ""])

            for finding in errors:
                lines.append(self._format_finding(finding))

            lines.append("")

        if warnings:
            lines.extend(["## Warnings", ""])

            for finding in warnings:
                lines.append(self._format_finding(finding))

            lines.append("")

        if infos:
            lines.extend(["## Information", ""])

            for finding in infos:
                lines.append(self._format_finding(finding))

            lines.append("")

        return "\n".join(lines)

    def save_markdown(
        self,
        report: Report,
        output_path: Path,
    ) -> None:
        """
        Save the Markdown report to disk.
        """

        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            self.to_markdown(report),
            encoding="utf-8",
        )

    @staticmethod
    def _format_finding(finding) -> str:
        """
        Format a single finding.
        """

        location = ""

        if finding.file:
            location = finding.file

            if finding.line is not None:
                location += f":{finding.line}"

        parts = [
            f"[{finding.severity.value}]",
            f"[{finding.rule_id}]",
        ]

        if location:
            parts.append(location)

        parts.append(finding.message)

        return " ".join(parts)