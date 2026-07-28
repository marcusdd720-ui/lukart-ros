from core.analysis.mime_detector import MimeDetector


class Document:
    def __init__(self, path):
        self.path = path
        self.mime_type = None


def test_pdf():

    detector = MimeDetector()

    doc = Document("document.pdf")

    detector.execute(doc)

    assert doc.mime_type == "application/pdf"


def test_txt():

    detector = MimeDetector()

    doc = Document("notes.txt")

    detector.execute(doc)

    assert doc.mime_type == "text/plain"


def test_unknown_extension():

    detector = MimeDetector()

    doc = Document("file.unknownextension")

    detector.execute(doc)

    assert doc.mime_type == "application/octet-stream"
