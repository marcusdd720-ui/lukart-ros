from dataclasses import dataclass


@dataclass
class Document:
    """
    Model dokumentu używany przez Analysis Pipeline.
    """

    path: str = ""
    text: str = ""

    language: str | None = None

    mime_type: str | None = None

    file_size: int | None = None

    created_at: float | None = None
    modified_at: float | None = None

    is_pdf: bool = False
    pdf_version: str | None = None

    requires_ocr: bool = False
