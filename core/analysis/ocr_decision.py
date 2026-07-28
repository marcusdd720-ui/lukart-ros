from core.analysis.chain import AnalysisHandler


class OCRDecision(AnalysisHandler):
    """
    Podejmuje decyzję, czy dokument wymaga OCR.
    """

    def handle(self, document):

        document.requires_ocr = False

        # OCR tylko dla PDF
        if not getattr(document, "is_pdf", False):
            return document

        # Brak tekstu -> OCR
        extracted_text = getattr(document, "text", None)

        if extracted_text is None:
            document.requires_ocr = True
            return document

        if len(extracted_text.strip()) == 0:
            document.requires_ocr = True
            return document

        return document
