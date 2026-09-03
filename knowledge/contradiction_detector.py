"""Deterministic contradiction detection for structured claims."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FactClaim:
    """Comparable statement used by the contradiction gate."""

    subject: str
    predicate: str
    value: str
    source_document_id: str = ""

    def key(self) -> tuple[str, str]:
        return self.subject.strip().casefold(), self.predicate.strip().casefold()


@dataclass(frozen=True, slots=True)
class Contradiction:
    key: tuple[str, str]
    left: FactClaim
    right: FactClaim


def detect_contradictions(claims: list[FactClaim]) -> list[Contradiction]:
    """Return conflicting claims with the same subject/predicate and values."""
    grouped: dict[tuple[str, str], list[FactClaim]] = {}
    for claim in claims:
        grouped.setdefault(claim.key(), []).append(claim)

    findings: list[Contradiction] = []
    for key, group in sorted(grouped.items()):
        unique: dict[str, FactClaim] = {}
        for claim in group:
            unique.setdefault(claim.value.strip().casefold(), claim)
        values = sorted(unique.values(), key=lambda item: item.value.casefold())
        if len(values) < 2:
            continue
        first = values[0]
        for other in values[1:]:
            findings.append(Contradiction(key=key, left=first, right=other))
    return findings


def require_no_contradictions(claims: list[FactClaim]) -> None:
    findings = detect_contradictions(claims)
    if findings:
        raise ValueError(f"Contradictions detected: {len(findings)}")
