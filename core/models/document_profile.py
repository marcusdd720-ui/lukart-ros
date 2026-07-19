from dataclasses import dataclass


@dataclass
class DocumentProfile:
    """
    Opis dokumentu po analizie.
    """

    path: str

    extension: str

    mime: str

    exists: bool = False

    is_file: bool = False

    size: int = 0

    is_empty: bool = False

    pages: int = 1

    contains_text: bool = False

    contains_images: bool = False

    strategy: str = "UNKNOWN"