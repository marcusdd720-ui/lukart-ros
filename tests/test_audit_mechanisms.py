# ruff: noqa: E501
"""Regression tests for architectural hardening gates."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import PrivacyViolation, save_source_snapshot, validate_case_key
from core.private_evidence_v1 import digest_object
from knowledge.contradiction_detector import FactClaim, detect_contradictions
from knowledge.evidence_readiness import EvidenceRequirement, check_evidence_readiness
from knowledge.models.case_manifest import CaseManifest
from knowledge.provenance import EntityType, EpistemicStatus, ExtractedFact
from knowledge.timeline_validator import TimelineCheckEvent, validate_timeline
from scripts.dependency_boundary_check import runtime_factory_imports
from scripts.secret_scan import scan_text


class AuditKeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "audit-key"
        assert key_version == 1
        return b"A" * 32


def _snapshot_authorization() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-audit-worker",
        tenant_id="synthetic-audit-tenant",
        roles=("case-worker",),
        permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
        case_ids=("CASE-0001",),
    )


def _save_snapshot(source: Path, data_root: Path, repo_root: Path) -> Path:
    return save_source_snapshot(
        "CASE-0001",
        source,
        authorization=_snapshot_authorization(),
        key_provider=AuditKeyProvider(),
        tenant_id="synthetic-audit-tenant",
        key_id="audit-key",
        source_ref="synthetic-audit-source",
        data_root=data_root,
        repo_root=repo_root,
    )


def test_case_manifest_is_canonical_and_stable(tmp_path: Path) -> None:
    manifest = CaseManifest(case_key="CASE-0001", case_id="CASE-0001", document_ids=("doc-b", "doc-a", "doc-a"))
    path = manifest.save(tmp_path)
    loaded = CaseManifest.load(tmp_path)
    assert loaded.canonical_dict()["document_ids"] == ["doc-a", "doc-b"]
    assert loaded.digest() == manifest.digest()
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_contradiction_detector_finds_conflicting_claims() -> None:
    claims = [FactClaim("person", "status", "active"), FactClaim("person", "status", "inactive")]
    assert len(detect_contradictions(claims)) == 1


def test_evidence_readiness_rejects_required_missing_file(tmp_path: Path) -> None:
    result = check_evidence_readiness(tmp_path, [EvidenceRequirement("decision", "evidence/decision.pdf")])
    assert not result.ready
    assert result.missing == ("decision",)


def test_timeline_validator_requires_deterministic_order() -> None:
    events = [TimelineCheckEvent("b", date(2025, 2, 1)), TimelineCheckEvent("a", date(2025, 1, 1))]
    assert validate_timeline(events)


def test_secret_scan_detects_private_key_marker() -> None:
    marker = "-----BEGIN " + "PRIVATE KEY" + "-----"
    assert scan_text(marker)


def test_secret_scan_ignores_normal_text() -> None:
    assert scan_text("ordinary legal text") == []


def test_dependency_gate_allows_relative_imports(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge" / "ontology"
    knowledge.mkdir(parents=True)
    (knowledge / "service.py").write_text("from .factory import OntologyFactory\n", encoding="utf-8")
    (tmp_path / "core").mkdir()
    assert runtime_factory_imports(tmp_path) == []


def test_case_key_rejects_traversal() -> None:
    with pytest.raises(PrivacyViolation):
        validate_case_key("../outside")


def test_source_snapshot_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    data_root = tmp_path / "mvros"
    repo_root = tmp_path / "repo"
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")

    snapshot = _save_snapshot(source, data_root, repo_root)
    repeated = _save_snapshot(source, data_root, repo_root)

    envelope = json.loads(snapshot.read_text(encoding="utf-8"))
    assert repeated == snapshot
    assert snapshot.stem == digest_object(envelope).removeprefix("sha256:")
    assert b"source" not in snapshot.read_bytes()


def test_extracted_fact_exposes_epistemic_metadata() -> None:
    fact = ExtractedFact(
        value="123",
        entity_type=EntityType.CASE_NUMBER,
        source_document_id="doc-1",
        page=1,
        char_start=0,
        char_end=3,
        extractor_version="v1",
        source_document_sha256="0" * 64,
        extraction_method="regex",
        confidence=0.8,
        epistemic_status=EpistemicStatus.EXTRACTED,
    )
    assert fact.confidence == 0.8
