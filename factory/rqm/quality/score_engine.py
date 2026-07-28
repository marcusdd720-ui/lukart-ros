from __future__ import annotations

from factory.rqm.model import Result, Score, Severity


class ScoreEngine:
    """
    Calculates the overall quality score from provider results.
    """

    PENALTIES = {
        Severity.INFO: 0,
        Severity.WARNING: 2,
        Severity.ERROR: 10,
        Severity.CRITICAL: 25,
    }

    def calculate(self, results: list[Result]) -> Score:
        value = 100.0

        infos = 0
        warnings = 0
        errors = 0
        criticals = 0

        for result in results:
            for finding in result.findings:
                if finding.severity == Severity.INFO:
                    infos += 1

                elif finding.severity == Severity.WARNING:
                    warnings += 1

                elif finding.severity == Severity.ERROR:
                    errors += 1

                elif finding.severity == Severity.CRITICAL:
                    criticals += 1

                value -= self.PENALTIES[finding.severity]

        value = max(0.0, value)

        return Score(
            value=value,
            infos=infos,
            warnings=warnings,
            errors=errors,
            criticals=criticals,
        )
