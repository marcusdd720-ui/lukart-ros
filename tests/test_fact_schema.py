from dataclasses import fields

import pytest

from knowledge.fact_contract import FactContractValidator
from knowledge.provenance import EntityType, ExtractedFact

EXPECTED_FACT_FIELDS = (
    "value",
    "entity_type",
    "source_document_id",
    "page",
    "char_start",
    "char_end",
    "extractor_version",
    "source_document_sha256",
    "extraction_method",
)


def test_extracted_fact_schema_is_stable() -> None:
    assert tuple(field.name for field in fields(ExtractedFact)) == EXPECTED_FACT_FIELDS
    assert set(EntityType) == {
        EntityType.CASE_NUMBER,
        EntityType.DECISION_NUMBER,
        EntityType.PARTY,
        EntityType.DATE,
        EntityType.AMOUNT,
        EntityType.LEGAL_BASIS,
        EntityType.DECISION_OUTCOME,
        EntityType.DEADLINE,
        EntityType.BENEFIT_AMOUNT,
        EntityType.COURT_NAME,
        EntityType.INSURED_PERIOD,
        EntityType.OTHER,
    }


def test_schema_and_contract_reject_incomplete_provenance() -> None:
    fact = ExtractedFact(
        value="01.09.2026",
        entity_type=EntityType.DATE,
        source_document_id="DOC-1",
        page=1,
        char_start=0,
        char_end=10,
        extractor_version="test-v1",
        source_document_sha256="",
        extraction_method="",
    )

    errors = FactContractValidator().validate([fact])
    assert "source_document_sha256" in errors[0]
    assert "extraction_method" in errors[1]

    with pytest.raises(ValueError, match="Fact contract violation"):
        FactContractValidator().validate_or_raise([fact])
