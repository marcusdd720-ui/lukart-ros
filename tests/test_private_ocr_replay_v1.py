from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import core.case_ingestion as case_ingestion
import core.private_ocr_replay_v1 as ocr_replay
from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_derivation_v1 import (
    derive_utf8_text,
    record_environment_bound_text_derivation,
)
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore
from core.private_ocr_replay_v1 import (
    OCR_CONFIG_V1,
    OCR_TRANSFORM_ID_V1,
    OCR_TRANSFORM_VERSION_V1,
    verify_environment_bound_ocr_replay,
    write_ocr_replay_proof,
)


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "case-key"
        assert key_version == 1
        return b"R" * 32


def _store(root: Path) -> PrivateEvidenceStore:
    return PrivateEvidenceStore(
        root,
        key_provider=KeyProvider(),
        authorization=AuthorizationContext(
            subject_id="synthetic-ocr-replay-worker",
            tenant_id="synthetic-tenant",
            roles=("case-worker",),
            permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
            case_ids=("CASE-OCR-REPLAY",),
        ),
        tenant_id="synthetic-tenant",
        case_id="CASE-OCR-REPLAY",
        key_id="case-key",
    )


def _install_fake_tesseract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    observed: dict[str, bytes],
) -> Path:
    executable = tmp_path / "tesseract-synthetic"
    executable.write_bytes(b"synthetic-tesseract-binary-v1")
    monkeypatch.setattr(ocr_replay.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(case_ingestion.shutil, "which", lambda _: str(executable))

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=b"tesseract synthetic replay 1.0",
                stderr=b"",
            )
        assert args[1:3] == ["stdin", "stdout"]
        assert kwargs.get("input") == b"synthetic-image-bytes"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=observed["output"],
            stderr=b"",
        )

    monkeypatch.setattr(case_ingestion.subprocess, "run", fake_run)
    return executable


def _record_ocr(
    store: PrivateEvidenceStore,
    executable: Path,
    *,
    output_text: str = "synthetic OCR output\n",
    config: dict[str, object] | None = None,
):
    source = store.import_bytes(
        b"synthetic-image-bytes",
        source_ref="image-slot",
        media_type="image/png",
    )
    tool_identity = case_ingestion._tesseract_identity(executable)
    return record_environment_bound_text_derivation(
        store,
        source,
        output_text,
        transform_id=OCR_TRANSFORM_ID_V1,
        transform_version=OCR_TRANSFORM_VERSION_V1,
        config=dict(OCR_CONFIG_V1) if config is None else config,
        tool_identity=tool_identity,
    )


def test_environment_bound_ocr_replay_observes_exact_same_output_without_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    derivation = _record_ocr(store, executable)

    proof = verify_environment_bound_ocr_replay(store, derivation.derivation_receipt_digest)

    assert proof.status == "MATCH"
    assert proof.replay_class == "ENVIRONMENT_BOUND"
    assert proof.derivation_receipt_digest == derivation.derivation_receipt_digest
    assert proof.semantic_derivation_id == derivation.semantic_derivation_id
    assert proof.source_evidence_id == derivation.source.evidence_id
    assert proof.derived_evidence_id == derivation.derived.evidence_id
    assert proof.observed_output_id == derivation.derived.evidence_id
    assert proof.proof_id.startswith("sha256:")


def test_ocr_replay_detects_tool_binary_drift_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    derivation = _record_ocr(store, executable)
    executable.write_bytes(b"synthetic-tesseract-binary-v2")

    with pytest.raises(PrivateEvidenceError, match="environment drift"):
        verify_environment_bound_ocr_replay(store, derivation.derivation_receipt_digest)


def test_ocr_replay_detects_output_drift_with_same_recorded_tool_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    derivation = _record_ocr(store, executable)
    observed["output"] = b"different OCR output\x0c"

    with pytest.raises(PrivateEvidenceError, match="output mismatch"):
        verify_environment_bound_ocr_replay(store, derivation.derivation_receipt_digest)


def test_ocr_replay_rejects_unknown_config_and_deterministic_derivations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    wrong_config = _record_ocr(store, executable, config={"language": "eng", "psm": 6})

    with pytest.raises(PrivateEvidenceError, match="configuration"):
        verify_environment_bound_ocr_replay(store, wrong_config.derivation_receipt_digest)

    text_source = store.import_bytes(
        b"synthetic text\n",
        source_ref="text-slot",
        media_type="text/plain",
    )
    deterministic = derive_utf8_text(store, text_source)
    with pytest.raises(PrivateEvidenceError, match="ENVIRONMENT_BOUND"):
        verify_environment_bound_ocr_replay(store, deterministic.derivation_receipt_digest)


def test_ocr_replay_enforces_source_and_output_budgets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    derivation = _record_ocr(store, executable)

    with pytest.raises(PrivateEvidenceError, match="source budget exceeded"):
        verify_environment_bound_ocr_replay(
            store,
            derivation.derivation_receipt_digest,
            max_source_bytes=1,
        )
    with pytest.raises(PrivateEvidenceError, match="output budget exceeded"):
        verify_environment_bound_ocr_replay(
            store,
            derivation.derivation_receipt_digest,
            max_output_bytes=1,
        )


def test_ocr_replay_proof_is_immutable_digest_only_and_cannot_enter_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"output": b"synthetic OCR output\x0c"}
    executable = _install_fake_tesseract(tmp_path, monkeypatch, observed=observed)
    store = _store(tmp_path / "evidence")
    derivation = _record_ocr(store, executable)
    proof = verify_environment_bound_ocr_replay(store, derivation.derivation_receipt_digest)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(PrivateEvidenceError, match="outside the public repository"):
        write_ocr_replay_proof(proof, repo_root / "proof.json", repo_root=repo_root)

    target = tmp_path / "private" / "proof.json"
    assert write_ocr_replay_proof(proof, target, repo_root=repo_root) == target
    assert write_ocr_replay_proof(proof, target, repo_root=repo_root) == target
    assert b"synthetic OCR output" not in target.read_bytes()

    changed = replace(proof, status="DIFFERENT")
    with pytest.raises(PrivateEvidenceError, match="divergence"):
        write_ocr_replay_proof(changed, target, repo_root=repo_root)
