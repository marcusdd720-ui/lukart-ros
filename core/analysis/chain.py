from abc import ABC, abstractmethod
from typing import Any, Optional


class AnalysisHandler(ABC):
    """
    Bazowa klasa analizatora w łańcuchu odpowiedzialności.
    """

    def __init__(self):
        self._next: Optional["AnalysisHandler"] = None

    def set_next(self, handler: "AnalysisHandler") -> "AnalysisHandler":
        self._next = handler
        return handler

    def execute(self, document: Any):

        result = self.handle(document)

        if self._next:
            return self._next.execute(result)

        return result

    @abstractmethod
    def handle(self, document: Any):
        pass