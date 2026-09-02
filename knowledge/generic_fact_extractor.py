"""Conservative, domain-neutral regex fact extractor.

This module is independent from the synthetic KQM benchmark. Patterns are
configuration-driven so production integrations can add domain-specific rules
without coupling the runtime pipeline to benchmark fixtures.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from knowledge.provenance import EntityType, ExtractedFact


@dataclass(frozen=True, slots=True)
class FactPattern:
    """A typed regular-expression rule used by the production baseline."""

    entity_type: EntityType
    pattern: str
    flags: int = 0
    group: int = 0


DEFAULT_PATTERNS: tuple[FactPattern, ...] = (
    FactPattern(EntityType.CASE_NUMBER, r"\b(?:Sygn\.?\s*akt|sygnatura)\s*[:.]?\s*[A-ZŁŚŻŹĆŃÓĘĄ0-9/-]+\b", re.IGNORECASE),
    FactPattern(EntityType.DECISION_NUMBER, r"\b(?:znak|nr\s+decyzji)\s*[:.]?\s*[A-ZŁŚŻŹĆŃÓĘĄ0-9/-]+\b", re.IGNORECASE),
    FactPattern(EntityType.DATE, r"\b(?:0?[1-9]|[12]\d|3[01])[.]\d{2}[.]\d{4}\b"),
    FactPattern(EntityType.AMOUNT, r"\b\d{1,9}(?:[ .]\d{3})*(?:,\d{2})?\s*(?:zł|PLN)\b", re.IGNORECASE),
    FactPattern(EntityType.LEGAL_BASIS, r"\bart\.\s*\d+[a-zA-Z]?\s*(?:§\s*\d+\s*)?(?:ust\.\s*\d+\s*)?(?:pkt\s*\d+\s*)?", re.IGNORECASE),
)


class GenericRegexFactExtractor:
    """Extract high-precision, source-bound facts using configured rules."""

    version = "regex-generic-v1"

    def __init__(self, patterns: Iterable[FactPattern] = DEFAULT_PATTERNS):
        self.patterns = tuple(patterns)

    def __call__(
        self,
        document_id: str,
        document_type: str,
        text: str,
    ) -> Iterable[ExtractedFact]:
        del document_type
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        facts: list[ExtractedFact] = []
        for rule in self.patterns:
            compiled = re.compile(rule.pattern, rule.flags)
            for match in compiled.finditer(text):
                start, end = match.span(rule.group)
                value = text[start:end].strip()
                if not value:
                    continue
                facts.append(
                    ExtractedFact(
                        value=value,
                        entity_type=rule.entity_type,
                        source_document_id=document_id,
                        page=1,
                        char_start=start,
                        char_end=end,
                        extractor_version=self.version,
                        source_document_sha256=source_hash,
                        extraction_method="deterministic_regex",
                    )
                )
        return sorted(
            facts,
            key=lambda fact: (
                fact.char_start,
                fact.char_end,
                fact.entity_type.value,
                fact.value,
            ),
        )


def build_pattern_map(
    patterns: Mapping[str, FactPattern],
) -> tuple[FactPattern, ...]:
    """Return named rules in deterministic order for configuration tooling."""
    return tuple(patterns[name] for name in sorted(patterns))
