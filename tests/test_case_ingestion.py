from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.case_ingestion import IngestionError, ingest_directory
from core.enterprise.contracts import AuthorizationContext, Permission
from knowledge.fact_extractor import extract_facts
from knowledge.models.case_manifest import CaseManifest
from knowledge.models.local_case_runtime import build_local_case_workspace


class TestKeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "test-key"
        assert key_version == 1
        return b"K" * 32


def _authorization(case_id: str = "CASE-0001") -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-worker",
        tenant_id="synthetic-tenant",
        roles=("case-worker",),
        permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
        case_ids=(case_id,),
    )


def _ingest(case_dir: Path, source: Path) -> list[object]:
    return ingest_directory(
        case_dir,
        source,
        authorization=_authorization(case_dir.name),
        key_provider=TestKeyProvider(),
        tenant_id="synthetic-tenant",
        key_id="test-key",
    )


def test_ingest_text_document_creates_encrypted_inventory_and_manifest(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    payload = "Synthetic private evidence payload.\n"
    source_file = source / "synthetic-input.txt"
    source_file.write_text(payload, encoding="utf-8")

    case_dir = tmp_path / "cases" / "CASE-0001"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-0001", case_id="CASE-0001").save(case_dir)

    documents = _ingest(case_dir, source)

    assert len(documents) == 1
    document = documents[0]
    assert document.evidence_id.startswith("sha256:")
    assert document.encrypted_path.is_file()
    assert not (case_dir / "original").exists()
    assert not (case_dir / "extracted").exists()
    assert not (case_dir / "markdown").exists()

    inventory_path = case_dir / "document_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory[0]["document_id"] == document.document_id
    assert inventory[0]["evidence_id"] == document.evidence_id
    assert "source_name" not in inventory[0]
    assert "original_path" not in inventory[0]
    assert "synthetic-input.txt" not in inventory_path.read_text(encoding="utf-8")
    manifest = CaseManifest.load(case_dir)
    assert manifest.document_ids == (document.document_id,)

    encoded = payload.encode("utf-8")
    for path in case_dir.rglob("*"):
        if path.is_file():
            assert encoded not in path.read_bytes()


def test_ingest_rejects_symlink_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "secret.txt"
    target.write_text("synthetic secret", encoding="utf-8")
    try:
        (source / "linked.txt").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")

    case_dir = tmp_path / "cases" / "CASE-0001"
    case_dir.mkdir(parents=True)
    with pytest.raises(IngestionError):
        _ingest(case_dir, source)


def test_ingest_fails_closed_without_authorization_and_key_provider(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "document.txt").write_text("synthetic", encoding="utf-8")
    case_dir = tmp_path / "CASE-0001"

    with pytest.raises(IngestionError, match="requires authorization"):
        ingest_directory(case_dir, source)


def test_real_case_document_type_is_accepted_without_synthetic_fact_generation() -> None:
    facts = list(extract_facts("DOC-001", "real_case", "art. 1 ustawy przykładowej"))
    assert facts == []


def test_local_runtime_attaches_encrypted_primary_evidence(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases" / "CASE-0001"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-0001", case_id="CASE-0001").save(case_dir)
    source = tmp_path / "source"
    source.mkdir()
    (source / "synthetic.txt").write_text("Synthetic source.\n", encoding="utf-8")
    _ingest(case_dir, source)

    workspace = build_local_case_workspace("CASE-0001", data_root=tmp_path)

    assert len(workspace.case.evidence_items) == 1
    evidence = workspace.case.evidence_items[0]
    assert evidence.weight.value == "primary"
    assert evidence.source.startswith("private-evidence:sha256:")
    assert evidence.metadata["local_only"] is True
    assert evidence.metadata["encrypted_at_rest"] is True
    assert workspace.graph.node_count() == 2
