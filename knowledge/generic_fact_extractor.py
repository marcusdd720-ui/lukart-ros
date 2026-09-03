"""Conservative, context-aware regex fact extractor.

The default rules remain deterministic and model-free. They extract values only when
an explicit textual cue establishes the entity role, which reduces false positives
while keeping the runtime independent from benchmark-specific literal values.
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


_NAME_CHARS = "A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż"
_TOKEN_CHARS = "A-ZŁŚŻŹĆŃÓĘĄ0-9"

DEFAULT_PATTERNS: tuple[FactPattern, ...] = (
    FactPattern(
        EntityType.CASE_NUMBER,
        rf"\b(?:Sygn\.?\s*akt|sygnatura|spraw(?:a|ie|ę))\s*[:.]?\s*"
        rf"((?:[IVXLCDM]+\s+[{_NAME_CHARS}]{{1,5}}\s+\d+(?:/\d+)?)|"
        rf"(?:[{_TOKEN_CHARS}][{_TOKEN_CHARS}-]*(?:/[{_TOKEN_CHARS}-]+)+))\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.DECISION_NUMBER,
        rf"\b(?:decyzja|znak|nr\s+decyzji)\s*[:.]?\s*"
        rf"([{_TOKEN_CHARS}][{_TOKEN_CHARS}-]*(?:/[{_TOKEN_CHARS}-]+)+)\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.INSURED_PERIOD,
        r"\b(?:za\s+okres|okres)\s+"
        r"((?:0?[1-9]|[12]\d|3[01])[.]\d{2}[.]\d{4}\s*[-–]\s*"
        r"(?:0?[1-9]|[12]\d|3[01])[.]\d{2}[.]\d{4})\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.DATE,
        r"\b(?:z\s+dnia|zawarta|data|sporządzono\s+dnia)\s+"
        r"((?:0?[1-9]|[12]\d|3[01])[.]\d{2}[.]\d{4})\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.BENEFIT_AMOUNT,
        r"\b(?:świadczenie|zasiłek|świadczenia|zasiłku)\s+"
        r"(\d{1,9}(?:[ .]\d{3})*(?:,\d{2})?\s*(?:zł|PLN))\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.AMOUNT,
        r"\b(?:kwot(?:a|ę|y)|należność|wartość)\s+"
        r"(\d{1,9}(?:[ .]\d{3})*(?:,\d{2})?\s*(?:zł|PLN))\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.LEGAL_BASIS,
        rf"\bart\.\s*\d+[a-zA-Z]?\s*"
        rf"(?:§\s*\d+\s*)?(?:ust\.\s*\d+\s*)?(?:pkt\s*\d+\s*)?"
        rf"(?:ustawy\s+[{_NAME_CHARS}-]+(?:\s+[{_NAME_CHARS}-]+)*)?",
        re.IGNORECASE,
    ),
    FactPattern(
        EntityType.DECISION_OUTCOME,
        rf"\bwynik\s*:\s*([{_NAME_CHARS}-]+)\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.PARTY,
        rf"\bprzez\s+stronę\s+"
        rf"([A-ZŁŚŻŹĆŃÓĘĄ][{_NAME_CHARS}'-]*(?:\s+[A-ZŁŚŻŹĆŃÓĘĄ][{_NAME_CHARS}'-]*){{0,3}})\b",
        group=1,
    ),
    FactPattern(
        EntityType.DEADLINE,
        r"\btermin(?:\s+procesowy)?\s*:\s*(\d+\s*dni)\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.DEADLINE,
        r"\btermin\s+((?:0?[1-9]|[12]\d|3[01])[.]\d{2}[.]\d{4})\b",
        re.IGNORECASE,
        group=1,
    ),
    FactPattern(
        EntityType.OTHER,
        rf"\bumowa\s+([{_TOKEN_CHARS}][{_TOKEN_CHARS}-]+)\b",
        re.IGNORECASE,
        group=1,
    ),
)


class GenericRegexFactExtractor:
    """Extract high-precision, source-bound facts using configured rules."""

    version = "regex-generic-v2"

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
