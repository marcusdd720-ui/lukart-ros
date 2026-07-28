from core.analysis.ocr_decision import OCRDecision


class Document:
    def __init__(self):
        self.is_pdf = False
        self.text = None
        self.requires_ocr = False


def test_non_pdf():

    detector = OCRDecision()

    doc = Document()

    detector.execute(doc)

    assert doc.requires_ocr is False


def test_pdf_without_text():

    detector = OCRDecision()

    doc = Document()

    doc.is_pdf = True
    doc.text = None

    detector.execute(doc)

    assert doc.requires_ocr is True


def test_pdf_empty_text():

    detector = OCRDecision()

    doc = Document()

    doc.is_pdf = True
    doc.text = ""

    detector.execute(doc)

    assert doc.requires_ocr is True


def test_pdf_with_text():

    detector = OCRDecision()

    doc = Document()

    doc.is_pdf = True
    doc.text = "To jest dokument PDF."

    detector.execute(doc)

    assert doc.requires_ocr is False
