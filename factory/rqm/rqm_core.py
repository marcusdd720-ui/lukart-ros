"""
RQM 4.0 – Orchestrator
"""

from __future__ import annotations

from pathlib import Path

from factory.rqm.model import Report
from factory.rqm.provider.provider_registry import ProviderRegistry
from factory.rqm.quality.quality_engine import QualityEngine

__all__ = ["RQMCore"]


class RQMCore:
    """
    Release Quality Manager orchestrator.

    Responsibilities
    ----------------
    - initialize ProviderRegistry
    - initialize QualityEngine
    - execute quality analysis
    - return a unified Report

    Business logic belongs to dedicated components.
    """

    def __init__(
        self,
        root: Path | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self.root = (root or Path.cwd()).resolve()
        self.registry = registry or ProviderRegistry.default()

        self.engine = QualityEngine(
            root=self.root,
            registry=self.registry,
        )

    def run(self) -> Report:
        """
        Execute Release Quality Manager.
        """
        return self.engine.run()