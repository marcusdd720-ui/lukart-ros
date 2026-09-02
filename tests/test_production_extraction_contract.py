import pytest

from knowledge.provenance import EntityType, ExtractedFact
from validation.production_extraction_contract import (
    ProductionExtractionContract,
    ProductionExtractionError,
)


def _fact(
    value: str = "01.09.2026",
    *,
    start: int = 0,
    end: int = 10,
    digest: str = "a" * 64,
) -> ExtractedFact:
    return ExtractedFact(
        value=value,
        entity_type=EntityType.DATE,
        source_document_id="DOC-1",
        page=1,
        char_start=start,
        char_end=end,
        extractor_version="prod-v1",
        source_document_sha256=digest,
        extraction_method="deterministic_regex",
    )


def test_accept_returns_deterministically_ordered_facts() -> None:
    facts = [_fact(start=10, end=20), _fact(start=0, end=10)]

    result = ProductionExtractionContract().accept(facts)

    assert [fact.char_start for fact in result.facts] == [0, 10]


def test_accept_deduplicates_same_evidence_occurrence() -> None:
    facts = [_fact(), _fact()]

    result = ProductionExtractionContract().accept(facts)

    assert len(result.facts) == 1


def test_accept_rejects_incomplete_provenance() -> None:
    invalid = _fact(digest="invalid")

    with pytest.raises(ProductionExtractionError, match="source_document_sha256"):
        ProductionExtractionContract().accept([invalid])


def test_accept_fails_closed_on_identity_conflict() -> None:
    conflicting = [_fact(value="01.09.2026"), _fact(value="02.09.2026")]

    with pytest.raises(ProductionExtractionError, match="conflicting facts share identity"):
        ProductionExtractionContract().accept(conflicting)
