"""Deterministic fact extraction adapter used by KQM experiments.

The extractor is deliberately independent of the gold corpus. It operates only on
(document_id, document_type, text) and emits the repository's ExtractedFact contract.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from knowledge.provenance import EntityType, ExtractedFact

_PATTERN_DEFINITIONS: dict[str, tuple[EntityType, str]] = {
    "case_number": (EntityType.CASE_NUMBER, r"\bSYN-CASE-\d{3}/\d{2}\b"),
    "decision_number": (EntityType.DECISION_NUMBER, r"\bSYN-DEC-\d{3}/\d{2}\b"),
    "decision_date": (EntityType.DATE, r"(?<=z dnia )\d{2}\.\d{2}\.\d{4}"),
    "contract_date": (EntityType.DATE, r"(?<=zawarta )\d{2}\.\d{2}\.\d{4}"),
    "amount": (EntityType.AMOUNT, r"\b\d{3,5},\d{2}\s+zł\b"),
    "legal_basis": (
        EntityType.LEGAL_BASIS,
        r"art\.\s+\d+\s+ustawy\s+przykładowej",
    ),
    "deadline_days": (EntityType.DEADLINE, r"\b\d+\s+dni\b"),
    "contract_deadline": (
        EntityType.DEADLINE,
        r"(?<=termin )\d{2}\.\d{2}\.\d{4}",
    ),
    "insured_period": (
        EntityType.INSURED_PERIOD,
        r"\b\d{2}\.\d{2}\.\d{4}-\d{2}\.\d{2}\.\d{4}\b",
    ),
    "benefit_amount": (
        EntityType.BENEFIT_AMOUNT,
        r"\b\d{3,5},\d{2}\s+zł\b",
    ),
    "outcome": (
        EntityType.DECISION_OUTCOME,
        r"(?<=Wynik: )(?:uwzględniono|oddalono|przyznano|odmówiono)",
    ),
}

_PARTY_PATTERN = re.compile(r"\bstron(?:ę|a)\s+([A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]*)")

_DOCUMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "wyrok_sadowy": ("case_number", "decision_date", "amount", "legal_basis", "outcome"),
    "decyzja_zus": (
        "decision_number",
        "decision_date",
        "benefit_amount",
        "insured_period",
        "outcome",
    ),
    "umowa": ("contract_date", "amount", "contract_deadline"),
    "pismo_procesowe": ("case_number", "decision_date", "legal_basis", "deadline_days"),
}


def _make_fact(
    *,
    document_id: str,
    entity_type: EntityType,
    text: str,
    start: int,
    end: int,
) -> ExtractedFact:
    return ExtractedFact(
        value=text[start:end],
        entity_type=entity_type,
        source_document_id=document_id,
        page=1,
        char_start=start,
        char_end=end,
        extractor_version="regex-kqm-v1",
        source_document_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        extraction_method="deterministic_regex",
    )


def extract_facts(document_id: str, document_type: str, text: str) -> Iterable[ExtractedFact]:
    """Extract typed facts with reproducible source spans from one document."""

    if document_type not in _DOCUMENT_PATTERNS:
        raise ValueError(f"unsupported document type: {document_type}")

    matches: list[ExtractedFact] = []
    for pattern_name in _DOCUMENT_PATTERNS[document_type]:
        entity_type, pattern = _PATTERN_DEFINITIONS[pattern_name]
        for match in re.finditer(pattern, text):
            matches.append(
                _make_fact(
                    document_id=document_id,
                    entity_type=entity_type,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                )
            )

    if document_type in {"umowa", "pismo_procesowe"}:
        for match in _PARTY_PATTERN.finditer(text):
            matches.append(
                _make_fact(
                    document_id=document_id,
                    entity_type=EntityType.PARTY,
                    text=text,
                    start=match.start(1),
                    end=match.end(1),
                )
            )

    return sorted(matches, key=lambda fact: (fact.char_start, fact.char_end, fact.entity_type.value))
