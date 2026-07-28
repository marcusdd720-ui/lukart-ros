from datetime import datetime
from pathlib import Path

from core.analysis.chain import AnalysisHandler


class MetadataDetector(AnalysisHandler):
    """
    Uzupełnia dokument o metadane systemowe.
    """

    def handle(self, document):

        path = Path(document.path)

        if not path.exists():
            raise FileNotFoundError(document.path)

        stat = path.stat()

        document.file_size = stat.st_size
        document.created_at = datetime.fromtimestamp(stat.st_ctime)
        document.modified_at = datetime.fromtimestamp(stat.st_mtime)

        return document
