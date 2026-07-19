from pathlib import Path


class DocumentClassifier:
    """
    Classifies documents based on file extension.
    """

    DOCUMENT_TYPES = {
        ".pdf": "PDF",
        ".doc": "DOC",
        ".docx": "DOCX",
        ".txt": "TEXT",
        ".md": "MARKDOWN",
        ".jpg": "IMAGE",
        ".jpeg": "IMAGE",
        ".png": "IMAGE",
        ".tif": "IMAGE",
        ".tiff": "IMAGE",
        ".eml": "EMAIL",
        ".msg": "EMAIL",
        ".zip": "ARCHIVE",
        ".xml": "XML",
    }

    def classify(self, file_path: str) -> str:

        extension = Path(file_path).suffix.lower()

        return self.DOCUMENT_TYPES.get(
            extension,
            "UNKNOWN"
        )