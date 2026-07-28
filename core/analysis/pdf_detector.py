from pathlib import Path

from core.analysis.chain import AnalysisHandler


class PDFDetector(AnalysisHandler):
    """
    Wykrywa poprawny plik PDF.
    """

    def handle(self, document):

        path = Path(document.path)

        document.is_pdf = False
        document.pdf_version = None

        if path.suffix.lower() != ".pdf":
            return document

        with path.open("rb") as f:
            header = f.read(8)

        if header.startswith(b"%PDF-"):
            document.is_pdf = True
            document.pdf_version = header[5:8].decode(
                "ascii",
                errors="ignore",
            )

        return document
