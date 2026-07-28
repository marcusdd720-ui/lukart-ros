from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from factory.rqm.model import Result


class BaseProvider(ABC):
    """
    Base class for all Release Quality Manager providers.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique provider name.
        """
        raise NotImplementedError

    @property
    def description(self) -> str:
        """
        Optional human-readable description.
        """
        return self.name

    @property
    def enabled(self) -> bool:
        """
        Indicates whether this provider should participate
        in the current quality run.
        """
        return True

    @abstractmethod
    def run(self) -> Result:
        """
        Execute provider checks and return a Common Domain Model Result.
        """
        raise NotImplementedError

    def __call__(self) -> Result:
        """
        Allow provider instances to be executed directly.
        """
        return self.run()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, root={str(self.root)!r})"
