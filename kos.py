import sys

from core.case_manager import CaseManager
from core.import_manager import ImportManager
from core.document_classifier import DocumentClassifier
from core.document_scanner import DocumentScanner
from core.document_pipeline import DocumentPipeline


def print_help():
    print("Knowledge Operating System")
    print()
    print("Available commands:")
    print("  new-case")
    print("  import <CASE-ID> <SOURCE_DIRECTORY>")
    print("  classify <FILE>")
    print("  scan <DIRECTORY>")
    print("  process <DIRECTORY>")


def main():

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1]

    if command == "new-case":

        manager = CaseManager()
        case_path = manager.create_case()

        print(f"✔ Created {case_path.name}")
        print(f"Location: {case_path}")

    elif command == "import":

        if len(sys.argv) != 4:
            print("Usage:")
            print('python kos.py import CASE-0001 "C:\\Documents"')
            return

        case_id = sys.argv[2]
        source_directory = sys.argv[3]

        manager = ImportManager()

        files, folders = manager.import_directory(
            case_id,
            source_directory
        )

        print()
        print("Import completed")
        print("------------------------------")
        print(f"CASE        : {case_id}")
        print(f"Files       : {files}")
        print(f"Folders     : {folders}")
        print(f"Destination : cases/{case_id}/original")

    elif command == "classify":

        if len(sys.argv) != 3:
            print("Usage:")
            print("python kos.py classify file.pdf")
            return

        classifier = DocumentClassifier()

        document_type = classifier.classify(sys.argv[2])

        print(f"Document type : {document_type}")

    elif command == "scan":

        if len(sys.argv) != 3:
            print("Usage:")
            print("python kos.py scan <DIRECTORY>")
            return

        scanner = DocumentScanner()

        documents = scanner.scan(sys.argv[2])

        print()
        print("Scan results")
        print("------------------------------")

        for document, document_type in documents:
            print(f"{document:<50} {document_type}")

        print("------------------------------")
        print(f"Total documents: {len(documents)}")

    elif command == "process":

        if len(sys.argv) != 3:
            print("Usage:")
            print("python kos.py process <DIRECTORY>")
            return

        scanner = DocumentScanner()
        pipeline = DocumentPipeline()

        documents = scanner.scan(sys.argv[2])

        print()
        print("Processing documents")
        print("------------------------------")

        for document, document_type in documents:
            processor = pipeline.process(document, document_type)
            print(f"{document:<50} -> {processor}")

        print("------------------------------")
        print(f"Processed documents: {len(documents)}")

    else:

        print(f"Unknown command: {command}")
        print()

        print_help()


if __name__ == "__main__":
    main()