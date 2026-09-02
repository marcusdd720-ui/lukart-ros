"""Public facade for the Release Quality Manager."""

from __future__ import annotations

from pathlib import Path

from factory.rqm.rqm import ReleaseQualityManager


class RQMFacade(ReleaseQualityManager):
    """Compatibility facade with a repository-root default."""

    def __init__(self, root: Path | None = None) -> None:
        super().__init__(root or Path.cwd())


__all__ = ["RQMFacade"]
