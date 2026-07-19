from dataclasses import dataclass
from typing import Optional


@dataclass
class Document:
    """
    Model dokumentu używany przez Analysis Pipeline.
    """

    path: str = ""
    text: str = ""

    language: Optional[str] = None

    mime_type: Optional[str] = None

    file_size: Optional[int] = None

    created_at: Optional[float] = None
    modified_at: Optional[float] = None

    is_pdf: bool = False
    pdf_version: Optional[str] = None

    requires_ocr: bool = False