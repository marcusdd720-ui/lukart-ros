from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    """
    Wynik ekstrakcji tekstu.
    """

    source: str

    text: str

    engine: str

    confidence: float = 1.0
