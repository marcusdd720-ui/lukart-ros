from dataclasses import dataclass


@dataclass(slots=True)
class Document:
    """
    Represents a discovered document.
    """

    path: str
    document_type: str
    extension: str
    size: int
