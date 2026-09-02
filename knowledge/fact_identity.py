"""Deterministic identity and deduplication for extracted facts.

Stage 7 establishes a conservative identity model: a fact is identified by its
source document, entity type, page, and exact character span. Value text and
extractor metadata are not part of the identity so extractor-version changes
do not create duplicate facts for the same evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.provenance import ExtractedFact


@dataclass(frozen=True, slots=True)
class FactIdentity:
    """Stable identity of one evidence occurrence in a source document."""

    source_document_id: str
    entity_type: str
    page: int
    char_start: int
    char_end: int

    @classmethod
    def from_fact(cls, fact: ExtractedFact) -> FactIdentity:
        return cls(
            source_document_id=fact.source_document_id,
            entity_type=fact.entity_type.value,
            page=fact.page,
            char_start=fact.char_start,
            char_end=fact.char_end,
        )

    def as_key(self) -> tuple[str, str, int, int, int]:
        return (
            self.source_document_id,
            self.entity_type,
            self.page,
            self.char_start,
            self.char_end,
        )


class FactIdentityConflict(ValueError):
    """Raised when one evidence identity maps to incompatible source content."""


def fact_identity(fact: ExtractedFact) -> FactIdentity:
    """Return the stable identity derived from a validated extracted fact."""
    return FactIdentity.from_fact(fact)


def deduplicate_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    """Collapse duplicate evidence occurrences deterministically.

    Facts with different source spans remain distinct even when their values
    are equal. A collision at the same identity is accepted only when the
    evidence content is identical; otherwise the function fails closed.
    """

    chosen: dict[FactIdentity, ExtractedFact] = {}
    for fact in sorted(
        facts,
        key=lambda item: (
            fact_identity(item).as_key(),
            item.value,
            item.source_document_sha256,
            item.extractor_version,
            item.extraction_method,
        ),
    ):
        identity = fact_identity(fact)
        existing = chosen.get(identity)
        if existing is None:
            chosen[identity] = fact
            continue

        if (
            existing.value != fact.value
            or existing.source_document_sha256 != fact.source_document_sha256
        ):
            raise FactIdentityConflict(
                "conflicting facts share identity "
                f"{identity.as_key()}: {existing.value!r} vs {fact.value!r}"
            )

    return [chosen[key] for key in sorted(chosen, key=FactIdentity.as_key)]


def duplicate_count(facts: list[ExtractedFact]) -> int:
    """Return the number of facts removed by deterministic deduplication."""
    return len(facts) - len(deduplicate_facts(facts))
