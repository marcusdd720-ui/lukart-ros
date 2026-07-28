from core.analyzer.document_analyzer import DocumentAnalyzer


def main():

    analyzer = DocumentAnalyzer()

    files = ["tests/test_document_analyzer.py", "README.md", "nie_istnieje.pdf"]

    for file in files:
        profile = analyzer.analyze(file)

        print("----------------------------------------")

        print("Path      :", profile.path)

        print("Exists    :", profile.exists)

        print("Is File   :", profile.is_file)

        print("Size      :", profile.size)

        print("Empty     :", profile.is_empty)

        print("Strategy  :", profile.strategy)


if __name__ == "__main__":
    main()
