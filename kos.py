"""Legacy KOS CLI retained for local-only case operations."""

from __future__ import annotations

import sys

from core.case_manager import CaseManager
from core.document_classifier import DocumentClassifier
from core.document_pipeline import DocumentPipeline
from core.document_scanner import DocumentScanner
from core.import_manager import ImportManager


def print_help() -> None:
    print("Knowledge Operating System")
    print()
    print("Real case storage is local-only and uses MVROS_DATA_ROOT or ~/MVROS-DATA.")
    print()
    print("Available commands:")
    print("  new-case")
    print("  import <CASE-ID> <LOCAL_SOURCE_DIRECTORY>")
    print("  classify <FILE>")
    print("  scan <DIRECTORY>")
    print("  process <DIRECTORY>")


def main() -> None:
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1]

    if command == "new-case":
        manager = CaseManager()
        case_path = manager.create_case()
        print(f"Created local private case: {case_path.name}")
        print(f"Location: {case_path}")

    elif command == "import":
        if len(sys.argv) != 4:
            print('Usage: python kos.py import <CASE-ID> "<LOCAL_SOURCE_DIRECTORY>"')
            return
        case_id = sys.argv[2]
        source_directory = sys.argv[3]
        manager = ImportManager()
        files, folders = manager.import_directory(case_id, source_directory)
        print("Import completed")
        print(f"CASE        : {case_id}")
        print(f"Files       : {files}")
        print(f"Folders     : {folders}")
        print("Storage     : private local MVROS_DATA_ROOT")

    elif command == "classify":
        if len(sys.argv) != 3:
            print("Usage: python kos.py classify file.pdf")
            return
        document_type = DocumentClassifier().classify(sys.argv[2])
        print(f"Document type : {document_type}")

    elif command == "scan":
        if len(sys.argv) != 3:
            print("Usage: python kos.py scan <DIRECTORY>")
            return
        documents = DocumentScanner().scan(sys.argv[2])
        print("Scan results")
        for document in documents:
            print(f"{document.path:<50} {document.document_type}")
        print(f"Total documents: {len(documents)}")

    elif command == "process":
        if len(sys.argv) != 3:
            print("Usage: python kos.py process <DIRECTORY>")
            return
        scanner = DocumentScanner()
        pipeline = DocumentPipeline()
        documents = scanner.scan(sys.argv[2])
        print("Processing documents")
        for document in documents:
            processor = pipeline.process(document, document.document_type)
            print(f"{document.path:<50} -> {processor}")
        print(f"Processed documents: {len(documents)}")

    else:
        print(f"Unknown command: {command}")
        print_help()


if __name__ == "__main__":
    main()
