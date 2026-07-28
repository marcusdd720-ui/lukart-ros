from pathlib import Path

from core.document import Document
from core.document_classifier import DocumentClassifier


class DocumentScanner:
    """
    Scans directories and returns Document objects.
    """

    def __init__(self):
        self.classifier = DocumentClassifier()

    def scan(self, directory: str) -> list[Document]:

        source = Path(directory)

        if not source.exists():
            raise FileNotFoundError(f"Directory '{source}' does not exist.")

        if not source.is_dir():
            raise NotADirectoryError(f"'{source}' is not a directory.")

        documents: list[Document] = []

        for file in source.rglob("*"):
            if not file.is_file():
                continue

            documents.append(
                Document(
                    path=str(file.relative_to(source)),
                    document_type=self.classifier.classify(str(file)),
                    extension=file.suffix.lower(),
                    size=file.stat().st_size,
                )
            )

        return documents
