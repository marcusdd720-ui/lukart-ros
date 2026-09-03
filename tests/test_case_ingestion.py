from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.case_ingestion import IngestionError, ingest_directory
from knowledge.fact_extractor import extract_facts
from knowledge.models.case_manifest import CaseManifest
from knowledge.models.local_case_runtime import build_local_case_workspace


def test_ingest_text_document_creates_original_extract_inventory_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    payload = "Pierwszy dokument sprawy.\n"
    source_file = source / "pismo.txt"
    source_file.write_text(payload, encoding="utf-8")

    case_dir = tmp_path / "data" / "cases" / "CASE-0001"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-0001", case_id="CASE-0001").save(case_dir)

    documents = ingest_directory(case_dir, source)

    assert len(documents) == 1
    document = documents[0]
    assert document.original_path.read_text(encoding="utf-8") == payload
    assert document.extracted_path.read_text(encoding="utf-8") == payload
    assert "Source SHA256" in document.markdown_path.read_text(encoding="utf-8")
    assert document.sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()

    inventory = json.loads((case_dir / "document_inventory.json").read_text(encoding="utf-8"))
    assert inventory[0]["document_id"] == document.document_id
    manifest = CaseManifest.load(case_dir)
    assert manifest.document_ids == (document.document_id,)


def test_ingest_rejects_symlink_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "secret.txt"
    target.write_text("secret", encoding="utf-8")
    (source / "linked.txt").symlink_to(target)

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    with pytest.raises(IngestionError):
        ingest_directory(case_dir, source)


def test_real_case_document_type_is_accepted_without_synthetic_fact_generation() -> None:
    facts = list(extract_facts("DOC-001", "real_case", "art. 1 ustawy przykładowej"))
    assert facts == []


def test_local_runtime_attaches_ingested_documents_as_primary_evidence(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases" / "CASE-0001"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-0001", case_id="CASE-0001").save(case_dir)
    source = tmp_path / "source"
    source.mkdir()
    (source / "dowod.txt").write_text("Dokument źródłowy.\n", encoding="utf-8")
    ingest_directory(case_dir, source)

    workspace = build_local_case_workspace("CASE-0001", data_root=tmp_path)

    assert len(workspace.case.evidence_items) == 1
    assert workspace.case.evidence_items[0].weight.value == "primary"
    assert workspace.case.evidence_items[0].metadata["local_only"] is True
    assert workspace.graph.node_count() == 2
