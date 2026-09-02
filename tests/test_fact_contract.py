import types
from typing import TypedDict, cast

import pytest

from knowledge.fact_contract import FactContractValidator
from knowledge.provenance import EntityType, ExtractedFact

_VALID_SHA256 = "a" * 64


class FactData(TypedDict):
    value: str
    entity_type: EntityType
    source_document_id: str
    page: int
    char_start: int
    char_end: int
    extractor_version: str
    source_document_sha256: str
    extraction_method: str


def _fact(**overrides: object) -> ExtractedFact:
    values: FactData = {
        "value": "01.09.2026",
        "entity_type": EntityType.DATE,
        "source_document_id": "DOC-1",
        "page": 1,
        "char_start": 0,
        "char_end": 10,
        "extractor_version": "test-v1",
        "source_document_sha256": _VALID_SHA256,
        "extraction_method": "deterministic_regex",
    }
    values.update(cast(FactData, overrides))
    return ExtractedFact(**values)


def _contract_fact(**overrides: object) -> ExtractedFact:
    values: FactData = {
        "value": "01.09.2026",
        "entity_type": EntityType.DATE,
        "source_document_id": "DOC-1",
        "page": 1,
        "char_start": 0,
        "char_end": 10,
        "extractor_version": "test-v1",
        "source_document_sha256": _VALID_SHA256,
        "extraction_method": "deterministic_regex",
    }
    values.update(cast(FactData, overrides))
    return cast(ExtractedFact, types.SimpleNamespace(**values))


def test_fact_contract_accepts_complete_provenance() -> None:
    assert FactContractValidator().validate([_fact()]) == []


def test_fact_contract_requires_source_hash() -> None:
    errors = FactContractValidator().validate([_fact(source_document_sha256="")])
    assert errors == [
        "fact[0]: source_document_sha256 must be a 64-character lowercase hexadecimal SHA-256"
    ]


def test_fact_contract_rejects_invalid_source_hash() -> None:
    errors = FactContractValidator().validate([_fact(source_document_sha256="abc123")])
    assert errors == [
        "fact[0]: source_document_sha256 must be a 64-character lowercase hexadecimal SHA-256"
    ]


def test_fact_contract_rejects_uppercase_source_hash() -> None:
    errors = FactContractValidator().validate([_fact(source_document_sha256="A" * 64)])
    assert errors == [
        "fact[0]: source_document_sha256 must be a 64-character lowercase hexadecimal SHA-256"
    ]


def test_fact_contract_requires_extraction_method() -> None:
    errors = FactContractValidator().validate([_fact(extraction_method="")])
    assert errors == ["fact[0]: extraction_method is required"]


def test_fact_contract_requires_extractor_version() -> None:
    errors = FactContractValidator().validate(
        [_contract_fact(extractor_version="")]
    )
    assert errors == ["fact[0]: extractor_version is required"]


def test_fact_contract_requires_non_whitespace_value() -> None:
    errors = FactContractValidator().validate([_contract_fact(value="   ")])
    assert errors == ["fact[0]: value must contain non-whitespace text"]


def test_fact_contract_raise_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="Fact contract violation"):
        FactContractValidator().validate_or_raise([_fact(source_document_sha256="")])
