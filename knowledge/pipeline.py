"""
Knowledge Operating System (KOS)

File: knowledge/pipeline.py
Version: 3.1
Sprint: F-013
"""

from __future__ import annotations

from knowledge.builder import GraphBuilder
from knowledge.extraction_stage import FactExtractionStage, FactExtractor
from knowledge.provenance import ExtractedFact
from knowledge.relation_engine import RelationEngine
from knowledge.report import GraphReport
from knowledge.validator import GraphValidator


class KnowledgePipeline:
    def __init__(
        self,
        root: str = ".",
        extractor: FactExtractor | None = None,
    ):
        self.builder = GraphBuilder(root)
        self.relations = RelationEngine()
        self.validator = GraphValidator()
        self.report = GraphReport()
        self.extraction = FactExtractionStage(extractor) if extractor else None
        self.extracted_facts: list[ExtractedFact] = []

    def run(self):
        print("=" * 60)
        print("Knowledge Operating System")
        print("Pipeline")
        print("=" * 60)

        print("[1/5] Building Graph...")
        graph = self.builder.build()
        print(f"      Nodes : {graph.node_count()}")

        print("[2/5] Fact Extraction...")
        if self.extraction is None:
            print("      SKIPPED (no extractor configured)")
        else:
            self.extracted_facts = self.extraction.run(self.builder.documents)
            print(f"      Facts : {len(self.extracted_facts)}")

        print("[3/5] Building Relations...")
        self.relations.run(graph)
        print(f"      Edges : {graph.edge_count()}")

        print("[4/5] Validation...")
        errors = self.validator.validate(graph)
        if errors:
            print(f"      FAILED ({len(errors)})")
            for error in errors:
                print("      -", error)
        else:
            print("      PASSED")

        print("[5/5] Report")
        print()
        print(self.report.generate(graph))
        return graph


def main():
    pipeline = KnowledgePipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
