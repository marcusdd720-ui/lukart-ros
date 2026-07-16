from pathlib import Path

from knowledge.document import Document


class DocumentLoader:
    """Pierwszy loader dokumentów KOS."""

    def __init__(self, root: str = "."):
        self.root = Path(root)

    def load_documents(self):
        """Zwraca listę obiektów Document."""
        documents = []

        for path in sorted(self.root.rglob("*.md")):
            documents.append(Document.from_file(path))

        return documents


if __name__ == "__main__":
    loader = DocumentLoader()

    documents = loader.load_documents()

    print("=" * 40)
    print("KOS Document Loader")
    print("=" * 40)

    for document in documents:
        print(
            f"{document.name} | "
            f"{document.extension} | "
            f"{document.size} bytes"
        )

    print("-" * 40)
    print(f"Documents found: {len(documents)}")