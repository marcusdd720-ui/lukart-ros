"""Tests for the production pipeline extraction stage."""

from datetime import datetime
from pathlib import Path

from knowledge.document import Document
from knowledge.extraction_stage import FactExtractionStage
from knowledge.metadata import Metadata
from knowledge.provenance import EntityType, ExtractedFact


def _document() -> Document:
    content = "SYNTHETIC FACT"
    return Document(
        path=Path("synthetic.md"),
        name="synthetic.md",
        extension=".md",
        size=len(content),
        modified=datetime(2026, 1, 1),
        metadata=Metadata(document_id="DOC-1", doc_type="synthetic"),
        content=content,
        logical_id="DOC-1",
    )


def _extractor(document_id: str, document_type: str, text: str):
    assert document_id == "DOC-1"
    assert document_type == "synthetic"
    assert text == "SYNTHETIC FACT"
    yield ExtractedFact(
        value="SYNTHETIC FACT",
        entity_type=EntityType.OTHER,
        source_document_id=document_id,
        page=1,
        char_start=0,
        char_end=len(text),
        extractor_version="test-v1",
        source_document_sha256="test-hash",
        extraction_method="test",
    )


def test_stage_extracts_from_loaded_documents() -> None:
    stage = FactExtractionStage(_extractor)

    facts = stage.run([_document()])

    assert len(facts) == 1
    assert facts[0].value == "SYNTHETIC FACT"
    assert stage.facts == facts


def test_stage_skips_documents_without_type() -> None:
    document = _document()
    document.metadata.doc_type = ""
    stage = FactExtractionStage(_extractor)

    assert stage.run([document]) == []
