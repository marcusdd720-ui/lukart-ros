"""Strict validation contract for extracted facts entering the knowledge graph."""

from __future__ import annotations

import re
from collections.abc import Iterable

from knowledge.provenance import EntityType, ExtractedFact

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FactContractValidator:
    """Validate facts against the production projection contract."""

    def validate(self, facts: Iterable[ExtractedFact]) -> list[str]:
        errors: list[str] = []
        for index, fact in enumerate(facts):
            prefix = f"fact[{index}]"
            if not fact.source_document_id.strip():
                errors.append(f"{prefix}: source_document_id is required")
            if not isinstance(fact.entity_type, EntityType):
                errors.append(f"{prefix}: entity_type must be an EntityType")
            if not fact.value.strip():
                errors.append(f"{prefix}: value must contain non-whitespace text")
            if fact.page < 1:
                errors.append(f"{prefix}: page must be >= 1")
            if fact.char_start < 0:
                errors.append(f"{prefix}: char_start must be >= 0")
            if fact.char_end <= fact.char_start:
                errors.append(f"{prefix}: char_end must be greater than char_start")
            if not fact.extractor_version.strip():
                errors.append(f"{prefix}: extractor_version is required")
            if not _SHA256_RE.fullmatch(fact.source_document_sha256):
                errors.append(
                    f"{prefix}: source_document_sha256 must be a 64-character lowercase hexadecimal SHA-256"
                )
            if not fact.extraction_method.strip():
                errors.append(f"{prefix}: extraction_method is required")
        return errors

    def validate_or_raise(self, facts: Iterable[ExtractedFact]) -> None:
        errors = self.validate(facts)
        if errors:
            raise ValueError("Fact contract violation: " + "; ".join(errors))
