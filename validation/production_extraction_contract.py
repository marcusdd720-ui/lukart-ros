"""Production extraction boundary enforcing the canonical fact contract."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.fact_contract import FactContractValidator
from knowledge.fact_identity import FactIdentityConflict, deduplicate_facts
from knowledge.provenance import ExtractedFact


class ProductionExtractionError(ValueError):
    """Raised when production extraction output violates its contract."""


@dataclass(frozen=True, slots=True)
class ProductionExtractionResult:
    """Validated, deterministically ordered production facts."""

    facts: tuple[ExtractedFact, ...]


class ProductionExtractionContract:
    """Validate, deduplicate, and freeze extractor output at the boundary."""

    def accept(self, facts: list[ExtractedFact]) -> ProductionExtractionResult:
        errors = FactContractValidator().validate(facts)
        if errors:
            raise ProductionExtractionError("; ".join(errors))
        try:
            normalized = deduplicate_facts(facts)
        except FactIdentityConflict as exc:
            raise ProductionExtractionError(str(exc)) from exc
        return ProductionExtractionResult(tuple(normalized))
