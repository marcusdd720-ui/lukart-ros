"""Document-to-fact extraction stage with explicit extractor injection."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from knowledge.document import Document
from knowledge.provenance import ExtractedFact

FactExtractor = Callable[[str, str, str], Iterable[ExtractedFact]]


@dataclass(slots=True)
class FactExtractionStage:
    """Run an extractor over loaded documents without coupling to benchmark data."""

    extractor: FactExtractor
    facts: list[ExtractedFact] = field(default_factory=list)

    def run(self, documents: Sequence[Document]) -> list[ExtractedFact]:
        extracted: list[ExtractedFact] = []
        for document in documents:
            document_id = document.metadata.document_id or document.logical_id or document.name
            document_type = document.metadata.doc_type
            if not document_id or not document_type:
                continue
            extracted.extend(self.extractor(document_id, document_type, document.content))

        self.facts = sorted(
            extracted,
            key=lambda fact: (
                fact.source_document_id,
                fact.char_start,
                fact.char_end,
                fact.entity_type.value,
            ),
        )
        return list(self.facts)
