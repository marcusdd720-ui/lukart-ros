import pytest

from knowledge.provenance import EntityType, ExtractedFact


def test_extracted_fact_preserves_reproducible_provenance() -> None:
    fact = ExtractedFact(
        value="III RC 956/25",
        entity_type=EntityType.CASE_NUMBER,
        source_document_id="doc-001",
        page=4,
        char_start=120,
        char_end=132,
        extractor_version="extractor-1.0.0",
        source_document_sha256="abc123",
        extraction_method="regex",
    )
    assert fact.entity_type is EntityType.CASE_NUMBER
    assert fact.page == 4
    assert fact.char_start == 120
    assert fact.char_end == 132
    assert fact.source_document_sha256 == "abc123"


def test_extracted_fact_rejects_invalid_span() -> None:
    with pytest.raises(ValueError, match="char_end"):
        ExtractedFact(
            value="x",
            entity_type=EntityType.OTHER,
            source_document_id="doc-001",
            page=1,
            char_start=10,
            char_end=10,
            extractor_version="1.0.0",
        )


def test_extracted_fact_is_immutable() -> None:
    fact = ExtractedFact(
        value="2026-01-01",
        entity_type=EntityType.DATE,
        source_document_id="doc-001",
        page=1,
        char_start=0,
        char_end=10,
        extractor_version="1.0.0",
    )
    with pytest.raises(AttributeError):
        fact.page = 2  # type: ignore[misc]
