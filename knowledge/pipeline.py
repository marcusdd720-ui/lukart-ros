"""
Knowledge Operating System (KOS)

File: knowledge/pipeline.py
Version: 2.0
Sprint: F-011
Status: Stable

Purpose:
Runs the complete KOS processing pipeline.
"""

from knowledge.builder import GraphBuilder
from knowledge.extractor import RelationExtractor
from knowledge.report import GraphReport
from knowledge.validator import GraphValidator


class KnowledgePipeline:

    def __init__(self, root="."):

        self.builder = GraphBuilder(root)
        self.extractor = RelationExtractor()
        self.validator = GraphValidator()
        self.report = GraphReport()

    def run(self):

        print("=" * 60)
        print("KOS Pipeline")
        print("=" * 60)

        print("[1/4] Building graph...")

        graph = self.builder.build()

        print(
            f"      Nodes : {graph.node_count()}"
        )

        print("[2/4] Extracting relations...")

        self.extractor.extract(graph)

        print(
            f"      Edges : {graph.edge_count()}"
        )

        print("[3/4] Validating...")

        errors = self.validator.validate(graph)

        if errors:
            print(
                f"      FAILED ({len(errors)} errors)"
            )
        else:
            print("      PASSED")

        print("[4/4] Report")

        print()

        print(
            self.report.generate(graph)
        )

        return graph


def main():

    pipeline = KnowledgePipeline()

    pipeline.run()


if __name__ == "__main__":
    main()