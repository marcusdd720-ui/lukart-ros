"""Tests for the dependency-injected KQM benchmark runner."""

import json  # noqa: I001
from pathlib import Path

from knowledge.provenance import EntityType, ExtractedFact
from validation.extraction_quality import build_split
from validation.kqm_runner import KQMRunner


CORPUS_PATH = Path("data/quality/extraction_gold_v1.json")
TAXONOMY_PATH = Path("docs/quality/critical_facts_schema.yaml")


def make_fact(
    document_id: str,
    entity_type: EntityType,
    value: str,
) -> ExtractedFact:
    return ExtractedFact(
        value=value,
        entity_type=entity_type,
        source_document_id=document_id,
        page=1,
        char_start=0,
        char_end=max(1, len(value)),
        extractor_version="runner-test-1",
        source_document_sha256="synthetic",
        extraction_method="test",
    )


def test_runner_loads_and_validates_corpus() -> None:
    runner = KQMRunner(CORPUS_PATH, TAXONOMY_PATH)
    gold, corpus = runner.load()

    assert len(gold) > 0
    assert corpus["document_count"] == 20


def test_runner_only_invokes_extractor_for_selected_split() -> None:
    runner = KQMRunner(CORPUS_PATH, TAXONOMY_PATH)
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    locked = build_split(payload, "locked_evaluation")
    seen: list[str] = []

    def extractor(
        document_id: str,
        document_type: str,
        text: str,
    ) -> list[ExtractedFact]:
        seen.append(document_id)
        return []

    runner.run(extractor, locked)

    assert set(seen) == set(locked.document_ids)


def test_runner_returns_metrics_from_injected_extractor() -> None:
    runner = KQMRunner(CORPUS_PATH, TAXONOMY_PATH)
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    development = build_split(payload, "development")
    gold, _ = runner.load()

    def extractor(
        document_id: str,
        document_type: str,
        text: str,
    ) -> list[ExtractedFact]:
        return [
            make_fact(item.document_id, item.entity_type, item.value)
            for item in gold
            if item.document_id == document_id
        ]

    metrics = runner.run(extractor, development)

    assert metrics.f1 == 1.0
    assert metrics.critical_recall == 1.0
    assert metrics.provenance_completeness == 1.0
