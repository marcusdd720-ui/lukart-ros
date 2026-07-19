from pathlib import Path

from core.analysis.metadata_detector import MetadataDetector


class Document:

    def __init__(self, path):
        self.path = str(path)
        self.file_size = None
        self.created_at = None
        self.modified_at = None


def test_metadata_detector(tmp_path):

    file = tmp_path / "sample.txt"
    file.write_text("KOS")

    detector = MetadataDetector()

    doc = Document(file)

    detector.execute(doc)

    assert doc.file_size == 3
    assert doc.created_at is not None
    assert doc.modified_at is not None


def test_missing_file():

    detector = MetadataDetector()

    doc = Document("does_not_exist.txt")

    try:
        detector.execute(doc)
        assert False
    except FileNotFoundError:
        assert True