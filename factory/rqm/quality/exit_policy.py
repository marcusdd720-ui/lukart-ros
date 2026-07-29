from __future__ import annotations

from factory.rqm.model import Decision


class ExitPolicy:
    """
    Maps release decisions to process exit codes.
    """

    EXIT_CODES = {
        Decision.READY_FOR_MERGE: 0,
        Decision.READY_WITH_WARNINGS: 0,
        Decision.NEEDS_REVIEW: 1,
        Decision.BLOCK_RELEASE: 1,
        Decision.UNKNOWN: 2,
    }

    def exit_code(self, decision: Decision) -> int:
        """
        Return the process exit code for a release decision.
        """
        return self.EXIT_CODES[decision]
    