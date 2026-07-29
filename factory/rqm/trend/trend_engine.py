from __future__ import annotations

from factory.rqm.model import Report
from factory.rqm.trend.trend import Trend, TrendDirection


class TrendEngine:
    """
    Computes the quality trend based on the current and previous score.
    """

    STABLE_THRESHOLD = 1.0

    def compute(
        self,
        report: Report,
        previous_score: float | None,
    ) -> Trend:
        """
        Compute quality trend.

        Parameters
        ----------
        report
            Current quality report.
        previous_score
            Previous overall quality score.

        Returns
        -------
        Trend
            Trend information.
        """

        if previous_score is None:
            return Trend(
                direction=TrendDirection.NEW,
                delta=0.0,
                previous_score=None,
            )

        delta = round(report.score - previous_score, 2)

        if delta >= self.STABLE_THRESHOLD:
            direction = TrendDirection.UP
        elif delta <= -self.STABLE_THRESHOLD:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.STABLE

        return Trend(
            direction=direction,
            delta=delta,
            previous_score=previous_score,
        )