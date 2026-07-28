from __future__ import annotations

from pathlib import Path

from validation.code_audit.models import AuditReport


class AuditReporter:
    def to_markdown(self, report: AuditReport) -> str:
        lines = [
            "# Code Audit Report",
            "",
            f"**ERRORS:** {len(report.errors)}",
            f"**WARNINGS:** {len(report.warnings)}",
            f"**INFO:** {len(report.infos)}",
            "",
            "---",
            "",
        ]

        if report.errors:
            lines.append("## ERRORS")
            for f in report.errors:
                loc = f"{f.file}:{f.line}" if f.line else f.file
                lines.append(f"- **{f.rule_id}** `{loc}` – {f.message}")
            lines.append("")

        if report.warnings:
            lines.append("## WARNINGS")
            for f in report.warnings:
                loc = f"{f.file}:{f.line}" if f.line else f.file
                lines.append(f"- **{f.rule_id}** `{loc}` – {f.message}")
            lines.append("")

        return "\n".join(lines)

    def save(self, report: AuditReport, output: Path) -> None:
        output.write_text(self.to_markdown(report), encoding="utf-8")
