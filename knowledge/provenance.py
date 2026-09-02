"""Evidence provenance contracts for extracted legal facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntityType(StrEnum):
    CASE_NUMBER = "CASE_NUMBER"
    DECISION_NUMBER = "DECISION_NUMBER"
    PARTY = "PARTY"
    DATE = "DATE"
    AMOUNT = "AMOUNT"
    LEGAL_BASIS = "LEGAL_BASIS"
    DECISION_OUTCOME = "DECISION_OUTCOME"
    DEADLINE = "DEADLINE"
    BENEFIT_AMOUNT = "BENEFIT_AMOUNT"
    COURT_NAME = "COURT_NAME"
    INSURED_PERIOD = "INSURED_PERIOD"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    """An extracted fact bound to a reproducible source location."""

    value: str
    entity_type: EntityType
    source_document_id: str
    page: int
    char_start: int
    char_end: int
    extractor_version: str
    source_document_sha256: str = ""
    extraction_method: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ExtractedFact.value must not be empty")
        if not self.source_document_id:
            raise ValueError("source_document_id must not be empty")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.char_start < 0:
            raise ValueError("char_start must be >= 0")
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if not self.extractor_version:
            raise ValueError("extractor_version must not be empty")
