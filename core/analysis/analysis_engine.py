from core.analyzer.document_analyzer import DocumentAnalyzer


class AnalysisEngine:
    """
    Główny silnik analizy dokumentów.
    """

    def __init__(self):
        self.document_analyzer = DocumentAnalyzer()

    def analyze(self, file_path):
        return self.document_analyzer.analyze(file_path)