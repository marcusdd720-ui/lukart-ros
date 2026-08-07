"""
Case object registry with business slugs.

Human works with slugs. System stores technical ids.
Lookup failures raise KeyError with clear context — never silent None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from knowledge.models.case import (
    Argument,
    EvidenceItem,
    Fact,
    LegalBasis,
    LegalIssue,
    TimelineEvent,
)

T = TypeVar("T")


class RegistryError(KeyError):
    """Missing or duplicate slug in CaseRegistry."""


@dataclass(slots=True)
class _Bucket(Generic[T]):
    kind: str
    items: dict[str, T] = field(default_factory=dict)

    def add(self, slug: str, obj: T) -> T:
        key = _norm(slug)
        if key in self.items:
            raise RegistryError(f"Duplicate {self.kind} slug: {slug!r}")
        self.items[key] = obj
        return obj

    def get(self, slug: str) -> T:
        key = _norm(slug)
        try:
            return self.items[key]
        except KeyError as exc:
            known = ", ".join(sorted(self.items)) or "(empty)"
            raise RegistryError(
                f"Unknown {self.kind} slug: {slug!r}. Known: {known}"
            ) from exc

    def id_of(self, slug: str) -> str:
        obj = self.get(slug)
        return obj.id  # type: ignore[attr-defined]

    def ids(self, *slugs: str) -> list[str]:
        return [self.id_of(s) for s in slugs]

    def all(self) -> list[T]:
        return list(self.items.values())

    def slugs(self) -> list[str]:
        return sorted(self.items)


def _norm(slug: str) -> str:
    s = (slug or "").strip()
    if not s:
        raise RegistryError("Slug cannot be empty")
    return s


@dataclass(slots=True)
class CaseRegistry:
    """
    Semantic registry for one case build.

    Usage:
        R = CaseRegistry()
        R.add_evidence("umowa_darowizny", item)
        R.E("umowa_darowizny")
        R.E_id("umowa_darowizny")
        R.E_ids("umowa_darowizny", "dowod_rejestracyjny")
    """

    evidence: _Bucket[EvidenceItem] = field(
        default_factory=lambda: _Bucket("evidence")
    )
    facts: _Bucket[Fact] = field(default_factory=lambda: _Bucket("fact"))
    timeline: _Bucket[TimelineEvent] = field(
        default_factory=lambda: _Bucket("timeline")
    )
    legal: _Bucket[LegalBasis] = field(default_factory=lambda: _Bucket("legal"))
    issues: _Bucket[LegalIssue] = field(default_factory=lambda: _Bucket("issue"))
    arguments: _Bucket[Argument] = field(
        default_factory=lambda: _Bucket("argument")
    )

    def add_evidence(self, slug: str, item: EvidenceItem) -> EvidenceItem:
        return self.evidence.add(slug, item)

    def add_fact(self, slug: str, item: Fact) -> Fact:
        return self.facts.add(slug, item)

    def add_timeline(self, slug: str, item: TimelineEvent) -> TimelineEvent:
        return self.timeline.add(slug, item)

    def add_legal(self, slug: str, item: LegalBasis) -> LegalBasis:
        return self.legal.add(slug, item)

    def add_issue(self, slug: str, item: LegalIssue) -> LegalIssue:
        return self.issues.add(slug, item)

    def add_argument(self, slug: str, item: Argument) -> Argument:
        return self.arguments.add(slug, item)

    def E(self, slug: str) -> EvidenceItem:
        return self.evidence.get(slug)

    def F(self, slug: str) -> Fact:
        return self.facts.get(slug)

    def T(self, slug: str) -> TimelineEvent:
        return self.timeline.get(slug)

    def L(self, slug: str) -> LegalBasis:
        return self.legal.get(slug)

    def I(self, slug: str) -> LegalIssue:
        return self.issues.get(slug)

    def A(self, slug: str) -> Argument:
        return self.arguments.get(slug)

    def E_id(self, slug: str) -> str:
        return self.evidence.id_of(slug)

    def F_id(self, slug: str) -> str:
        return self.facts.id_of(slug)

    def L_id(self, slug: str) -> str:
        return self.legal.id_of(slug)

    def I_id(self, slug: str) -> str:
        return self.issues.id_of(slug)

    def A_id(self, slug: str) -> str:
        return self.arguments.id_of(slug)

    def E_ids(self, *slugs: str) -> list[str]:
        return self.evidence.ids(*slugs)

    def F_ids(self, *slugs: str) -> list[str]:
        return self.facts.ids(*slugs)

    def L_ids(self, *slugs: str) -> list[str]:
        return self.legal.ids(*slugs)

    def I_ids(self, *slugs: str) -> list[str]:
        return self.issues.ids(*slugs)

    def A_ids(self, *slugs: str) -> list[str]:
        return self.arguments.ids(*slugs)

    def summary(self) -> dict[str, int]:
        return {
            "evidence": len(self.evidence.items),
            "facts": len(self.facts.items),
            "timeline": len(self.timeline.items),
            "legal": len(self.legal.items),
            "issues": len(self.issues.items),
            "arguments": len(self.arguments.items),
        }