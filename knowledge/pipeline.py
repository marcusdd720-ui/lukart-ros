"""
Knowledge Operating System (KOS)

File: knowledge/pipeline.py
Version: 3.0
Sprint: F-012
"""

from knowledge.builder import GraphBuilder
from knowledge.relation_engine import RelationEngine
from knowledge.report import GraphReport
from knowledge.validator import GraphValidator


class KnowledgePipeline:
    def __init__(self, root="."):

        self.builder = GraphBuilder(root)

        self.relations = RelationEngine()

        self.validator = GraphValidator()

        self.report = GraphReport()

    def run(self):

        print("=" * 60)
        print("Knowledge Operating System")
        print("Pipeline")
        print("=" * 60)

        print("[1/4] Building Graph...")

        graph = self.builder.build()

        print(f"      Nodes : {graph.node_count()}")

        print("[2/4] Building Relations...")

        self.relations.run(graph)

        print(f"      Edges : {graph.edge_count()}")

        print("[3/4] Validation...")

        errors = self.validator.validate(graph)

        if errors:
            print(f"      FAILED ({len(errors)})")

            for error in errors:
                print("      -", error)

        else:
            print("      PASSED")

        print("[4/4] Report")

        print()

        print(self.report.generate(graph))

        return graph


def main():

    pipeline = KnowledgePipeline()

    pipeline.run()


if __name__ == "__main__":
    main()
