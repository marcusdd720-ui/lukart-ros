"""Tests for the extraction-quality benchmark contract."""

import json  # noqa: I001
from pathlib import Path

import pytest

from knowledge.provenance import EntityType, ExtractedFact
from validation.extraction_quality import build_split, evaluate, load_corpus_documents


CORPUS_PATH = Path("data/quality/extraction_gold_v1.json")


def load_payload() -> dict[str, object]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def fact(
    document_id: str,
    entity_type: EntityType,
    value: str,
    *,
    extractor_version: str = "synthetic-test-1",
) -> ExtractedFact:
    return ExtractedFact(
        value=value,
        entity_type=entity_type,
        source_document_id=document_id,
        page=1,
        char_start=0,
        char_end=max(1, len(value)),
        extractor_version=extractor_version,
        source_document_sha256="synthetic",
        extraction_method="fixture",
    )


def test_corpus_has_research_charter_split() -> None:
    payload = load_payload()
    documents = payload["documents"]
    assert isinstance(documents, list)
    assert len(documents) == 20

    development = build_split(payload, "development")
    validation = build_split(payload, "validation")
    locked = build_split(payload, "locked_evaluation")

    assert len(development.document_ids) == 12
    assert len(validation.document_ids) == 4
    assert len(locked.document_ids) == 4
    assert set(development.document_ids).isdisjoint(validation.document_ids)
    assert set(development.document_ids).isdisjoint(locked.document_ids)
    assert set(validation.document_ids).isdisjoint(locked.document_ids)

    split_ids = (
        set(development.document_ids)
        | set(validation.document_ids)
        | set(locked.document_ids)
    )
    corpus_ids = {item["document_id"] for item in documents}
    assert split_ids == corpus_ids


def test_corpus_facts_are_versioned_and_typed() -> None:
    facts = load_corpus_documents(load_payload())
    assert facts
    assert all(isinstance(item.entity_type, EntityType) for item in facts)
    assert all(item.document_id.startswith("SYN-") for item in facts)


def test_perfect_predictions_reach_full_metrics() -> None:
    payload = load_payload()
    gold = load_corpus_documents(payload)
    locked = build_split(payload, "locked_evaluation")
    predictions = [
        fact(item.document_id, item.entity_type, item.value)
        for item in gold
        if locked.contains(item.document_id)
    ]

    metrics = evaluate(gold, predictions, split=locked)

    assert metrics.true_positive > 0
    assert metrics.false_positive == 0
    assert metrics.false_negative == 0
    assert metrics.precision == pytest.approx(1.0)
    assert metrics.recall == pytest.approx(1.0)
    assert metrics.f1 == pytest.approx(1.0)
    assert metrics.critical_recall == pytest.approx(1.0)
    assert metrics.critical_fact_loss == 0
    assert metrics.case_number_false_positive_rate == pytest.approx(0.0)
    assert metrics.provenance_completeness == pytest.approx(1.0)


def test_critical_recall_detects_a_missing_material_fact() -> None:
    payload = load_payload()
    gold = load_corpus_documents(payload)
    locked = build_split(payload, "locked_evaluation")
    locked_gold = [item for item in gold if locked.contains(item.document_id)]
    missing = next(item for item in locked_gold if item.critical)
    predictions = [
        fact(item.document_id, item.entity_type, item.value)
        for item in locked_gold
        if item is not missing
    ]

    metrics = evaluate(gold, predictions, split=locked)

    assert metrics.false_negative == 1
    assert metrics.critical_fact_loss == 1
    assert metrics.critical_recall < 1.0


def test_case_number_false_positive_rate_is_document_level() -> None:
    payload = load_payload()
    gold = load_corpus_documents(payload)
    locked = build_split(payload, "locked_evaluation")

    metrics = evaluate(
        gold,
        [fact("SYN-UM-004", EntityType.CASE_NUMBER, "SYN-CASE-FALSE/26")],
        split=locked,
    )

    assert metrics.case_number_false_positive_rate == pytest.approx(0.5)


def test_provenance_is_measured_for_predictions() -> None:
    payload = load_payload()
    gold = load_corpus_documents(payload)
    locked = build_split(payload, "locked_evaluation")
    metrics = evaluate(
        gold,
        [fact("SYN-UM-004", EntityType.PARTY, "Jantar")],
        split=locked,
    )

    assert metrics.provenance_completeness == pytest.approx(1.0)
    assert metrics.complete
