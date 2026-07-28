from __future__ import annotations

from abc import ABC, abstractmethod


class AnalysisHandler(ABC):
    """
    Bazowa klasa dla wszystkich analizatorów KOS.

    Implementuje wzorzec Chain of Responsibility.
    """

    def __init__(self):
        self._next = None

    def set_next(self, handler: AnalysisHandler) -> AnalysisHandler:
        """
        Łączy kolejny element pipeline.
        """
        self._next = handler
        return handler

    def execute(self, document):
        """
        Uruchamia analizator i przekazuje dokument dalej.
        """
        document = self.handle(document)

        if self._next:
            return self._next.execute(document)

        return document

    @abstractmethod
    def handle(self, document):
        """
        Implementacja konkretnego analizatora.
        """
        raise NotImplementedError
