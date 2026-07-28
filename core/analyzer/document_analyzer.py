from pathlib import Path

from core.analyzer.file_detector import FileDetector
from core.models.document_profile import DocumentProfile


class DocumentAnalyzer:
    IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def __init__(self):

        self.file_detector = FileDetector()

    def analyze(self, file_path: str) -> DocumentProfile:

        extension = Path(file_path).suffix.lower()

        profile = DocumentProfile(path=file_path, extension=extension, mime="")

        profile = self.file_detector.analyze(profile)

        if extension == ".pdf":
            profile.strategy = "PDF"

        elif extension in self.IMAGE_TYPES:
            profile.strategy = "OCR"

        elif extension == ".docx":
            profile.strategy = "DOCX"

        elif extension == ".doc":
            profile.strategy = "DOC"

        elif extension == ".txt":
            profile.strategy = "TXT"

        elif extension == ".eml":
            profile.strategy = "EML"

        else:
            profile.strategy = "UNKNOWN"

        return profile
