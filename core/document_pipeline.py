class DocumentPipeline:
    """
    Routes documents to the appropriate processing pipeline.
    """

    def process(self, file_path: str, document_type: str) -> str:
        """
        Selects the processor based on the document type.
        """

        processors = {
            "pdf": "PDF Processor",
            "docx": "DOCX Processor",
            "txt": "TXT Processor",
            "image": "OCR Processor",
        }

        return processors.get(document_type, "Unsupported Processor")