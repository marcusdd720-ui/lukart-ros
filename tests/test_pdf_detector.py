from core.analysis.pdf_detector import PDFDetector


class Document:
    def __init__(self, path):
        self.path = str(path)
        self.is_pdf = False
        self.pdf_version = None


def test_valid_pdf(tmp_path):

    file = tmp_path / "sample.pdf"

    file.write_bytes(b"%PDF-1.7\n")

    detector = PDFDetector()

    doc = Document(file)

    detector.execute(doc)

    assert doc.is_pdf
    assert doc.pdf_version == "1.7"


def test_not_pdf(tmp_path):

    file = tmp_path / "sample.txt"

    file.write_text("hello")

    detector = PDFDetector()

    doc = Document(file)

    detector.execute(doc)

    assert doc.is_pdf is False
