from __future__ import annotations

from factory.rqm.model import Decision, Score


class DecisionPolicy:
    """
    Determines the release decision based on the calculated quality score.

    Decision thresholds:

        95 - 100  -> READY_FOR_MERGE
        80 - 94   -> READY_WITH_WARNINGS
        60 - 79   -> NEEDS_REVIEW
         0 - 59   -> BLOCK_RELEASE
    """

    READY_FOR_MERGE_THRESHOLD = 95.0
    READY_WITH_WARNINGS_THRESHOLD = 80.0
    NEEDS_REVIEW_THRESHOLD = 60.0

    def decide(self, score: Score) -> Decision:
        """
        Determine the release decision.

        Parameters
        ----------
        score
            Overall project quality score.

        Returns
        -------
        Decision
            Release decision.
        """

        if score.value >= self.READY_FOR_MERGE_THRESHOLD:
            return Decision.READY_FOR_MERGE

        if score.value >= self.READY_WITH_WARNINGS_THRESHOLD:
            return Decision.READY_WITH_WARNINGS

        if score.value >= self.NEEDS_REVIEW_THRESHOLD:
            return Decision.NEEDS_REVIEW

        return Decision.BLOCK_RELEASE
