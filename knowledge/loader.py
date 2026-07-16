"""
Knowledge Operating System (KOS)

File: knowledge/loader.py
Sprint: F-009

Loads Markdown documents and parses metadata.
"""

from pathlib import Path

from knowledge.document import Document
from knowledge.metadata import MetadataParser


class DocumentLoader:
    """Loads Markdown documents from the repository."""

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.parser = MetadataParser()

    def load_documents(self):

        documents = []

        for path in sorted(self.root.rglob("*.md")):

            document = Document.from_file(path)

            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="utf-8", errors="ignore")

            document.metadata = self.parser.parse(text)

            documents.append(document)

        return documents


if __name__ == "__main__":

    loader = DocumentLoader()

    documents = loader.load_documents()

    print("=" * 50)
    print("KOS Document Loader")
    print("=" * 50)

    for document in documents:

        print(document.name)

        if document.metadata.document_id:
            print(f"  id      : {document.metadata.document_id}")
            print(f"  title   : {document.metadata.title}")
            print(f"  type    : {document.metadata.doc_type}")
            print(f"  version : {document.metadata.version}")
            print(f"  status  : {document.metadata.status}")

        print()

    print("=" * 50)
    print(f"Documents found: {len(documents)}")