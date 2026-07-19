import mimetypes

from core.analysis.chain import AnalysisHandler


class MimeDetector(AnalysisHandler):
    """
    Wykrywa MIME Type dokumentu na podstawie rozszerzenia.
    """

    def handle(self, document):

        mime, _ = mimetypes.guess_type(document.path)

        document.mime_type = mime or "application/octet-stream"

        return document