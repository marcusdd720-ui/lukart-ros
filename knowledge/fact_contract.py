"""Strict validation contract for extracted facts entering the knowledge graph."""

from __future__ import annotations

from collections.abc import Iterable

from knowledge.provenance import ExtractedFact


class FactContractValidator:
    """Validate facts against the production projection contract."""

    def validate(self, facts: Iterable[ExtractedFact]) -> list[str]:
        errors: list[str] = []
        for index, fact in enumerate(facts):
            prefix = f"fact[{index}]"
            if not fact.source_document_sha256:
                errors.append(f"{prefix}: source_document_sha256 is required")
            if not fact.extraction_method:
                errors.append(f"{prefix}: extraction_method is required")
            if not fact.value.strip():
                errors.append(f"{prefix}: value must contain non-whitespace text")
        return errors

    def validate_or_raise(self, facts: Iterable[ExtractedFact]) -> None:
        errors = self.validate(facts)
        if errors:
            raise ValueError("Fact contract violation: " + "; ".join(errors))
