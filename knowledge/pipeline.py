"""
Knowledge Operating System (KOS)

File: knowledge/pipeline.py
Version: 3.4
Sprint: FACT-003 / DEDUP-001
"""

from __future__ import annotations

from knowledge.builder import GraphBuilder
from knowledge.extraction_stage import FactExtractionStage, FactExtractor
from knowledge.fact_contract import FactContractValidator
from knowledge.fact_identity import deduplicate_facts
from knowledge.fact_projection import FactProjection
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
        self.projection = FactProjection()
        self.fact_contract = FactContractValidator()
        self.extracted_facts: list[ExtractedFact] = []

    def run(self):
        print("=" * 60)
        print("Knowledge Operating System")
        print("Pipeline")
        print("=" * 60)

        print("[1/7] Building Graph...")
        graph = self.builder.build()
        print(f"      Nodes : {graph.node_count()}")

        print("[2/7] Fact Extraction...")
        if self.extraction is None:
            print("      SKIPPED (no extractor configured)")
        else:
            self.extracted_facts = self.extraction.run(self.builder.documents)
            print(f"      Facts : {len(self.extracted_facts)}")

        print("[3/7] Fact Contract...")
        if not self.extracted_facts:
            print("      SKIPPED (no extracted facts)")
        else:
            self.fact_contract.validate_or_raise(self.extracted_facts)
            print("      PASSED")

        print("[4/7] Fact Identity + Deduplication...")
        if not self.extracted_facts:
            print("      SKIPPED (no extracted facts)")
        else:
            before = len(self.extracted_facts)
            self.extracted_facts = deduplicate_facts(self.extracted_facts)
            print(f"      Unique Facts : {len(self.extracted_facts)}")
            print(f"      Duplicates Removed : {before - len(self.extracted_facts)}")

        print("[5/7] Fact Projection...")
        if not self.extracted_facts:
            print("      SKIPPED (no extracted facts)")
        else:
            projected = self.projection.project(
                graph,
                self.builder.documents,
                self.extracted_facts,
            )
            print(f"      Fact Nodes : {len(projected)}")

        print("[6/7] Building Relations + Validation...")
        self.relations.run(graph)
        print(f"      Edges : {graph.edge_count()}")
        errors = self.validator.validate(graph)
        if errors:
            print(f"      FAILED ({len(errors)})")
            for error in errors:
                print("      -", error)
        else:
            print("      PASSED")

        print("[7/7] Report")
        print()
        print(self.report.generate(graph))
        return graph


def main():
    pipeline = KnowledgePipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
