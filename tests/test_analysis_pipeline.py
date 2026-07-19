from core.analysis.mime_detector import MimeDetector
from core.analysis.metadata_detector import MetadataDetector
from core.analysis.pdf_detector import PDFDetector
from core.analysis.ocr_decision import OCRDecision


class Document:

    def __init__(self, path):
        self.path = str(path)

        self.mime_type = None

        self.file_size = None
        self.created_at = None
        self.modified_at = None

        self.is_pdf = False
        self.pdf_version = None

        self.text = None
        self.requires_ocr = False


def test_pipeline(tmp_path):

    file = tmp_path / "sample.pdf"

    file.write_bytes(b"%PDF-1.0\n")

    mime = MimeDetector()
    metadata = MetadataDetector()
    pdf = PDFDetector()
    ocr = OCRDecision()

    mime.set_next(metadata).set_next(pdf).set_next(ocr)

    doc = Document(file)

    mime.execute(doc)

    assert doc.mime_type == "application/pdf"

    assert doc.file_size == 9
    assert doc.created_at is not None
    assert doc.modified_at is not None

    assert doc.is_pdf is True
    assert doc.pdf_version == "1.0"

    assert doc.requires_ocr is True