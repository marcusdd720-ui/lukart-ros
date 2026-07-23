from core.analysis.analysis_engine import AnalysisEngine


def main():

    engine = AnalysisEngine()

    files = [

        "tests/test_document_analyzer.py",

        "README.md",

        "nie_istnieje.pdf"

    ]

    for file in files:

        profile = engine.analyze(file)

        print("=" * 60)

        print("PATH       :", profile.path)

        print("EXISTS     :", profile.exists)

        print("SIZE       :", profile.size)

        print("EXTENSION  :", profile.extension)

        print("STRATEGY   :", profile.strategy)


if __name__ == "__main__":
    main()