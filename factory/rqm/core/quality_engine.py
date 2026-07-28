from __future__ import annotations

from pathlib import Path

from factory.rqm.provider import registry

from factory.rqm.model.quality_report import QualityReport


class QualityEngine:
    def __init__(self, root: Path):
        self.root = root

    def run(self) -> QualityReport:
        # Create provider instances
        providers = registry.create_all(self.root)

        # Execute all providers
        results = [provider.run() for provider in providers]

        # Return canonical quality report
        return QualityReport(
            providers=results,
        )
