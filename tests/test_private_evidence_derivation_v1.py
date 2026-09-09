from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_derivation_v1 import (
    MAX_TEXT_INPUT_BYTES,
    ReplayClass,
    derive_utf8_text,
    load_derivation,
    record_environment_bound_text_derivation,
    verify_derivation,
)
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "case-key"
        assert key_version == 1
        return b"D" * 32


def _authorization(case_id: str = "CASE-DERIVE") -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-derivation-worker",
        tenant_id="synthetic-tenant",
        roles=("case-worker",),
        permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
        case_ids=(case_id,),
    )


def _store(root: Path, *, case_id: str = "CASE-DERIVE") -> PrivateEvidenceStore:
    return PrivateEvidenceStore(
        root,
        key_provider=KeyProvider(),
        authorization=_authorization(case_id),
        tenant_id="synthetic-tenant",
        case_id=case_id,
        key_id="case-key",
    )


def test_utf8_derivation_is_deterministic_provenance_bound_and_encrypted(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"line-one\r\nline-two\rline-three\n",
        source_ref="source-slot",
        media_type="text/plain",
    )

    first = derive_utf8_text(store, source)
    second = derive_utf8_text(store, source)

    assert first == second
    assert first.replay_class is ReplayClass.DETERMINISTIC
    assert store.read(first.derived) == b"line-one\nline-two\nline-three\n"
    assert first.derivation_receipt_digest.startswith("sha256:")
    verify_derivation(store, first)

    plaintext = b"line-one\nline-two\nline-three\n"
    for path in store.root.rglob("*"):
        if path.is_file():
            assert plaintext not in path.read_bytes()


def test_derivation_rehydrates_by_digest_after_encrypted_backup_restore(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"offline\r\nreplay\n",
        source_ref="source-slot",
        media_type="text/plain",
    )
    original = derive_utf8_text(store, source)
    backup = store.backup_to(tmp_path / "backup")

    restored = PrivateEvidenceStore.restore_from(
        backup,
        tmp_path / "restored",
        key_provider=KeyProvider(),
        authorization=_authorization(),
        tenant_id="synthetic-tenant",
        case_id="CASE-DERIVE",
        key_id="case-key",
    )
    reloaded = load_derivation(restored, original.derivation_receipt_digest)

    assert reloaded.semantic_derivation_id == original.semantic_derivation_id
    assert reloaded.derivation_receipt_digest == original.derivation_receipt_digest
    assert reloaded.source.evidence_id == source.evidence_id
    assert reloaded.derived.evidence_id == original.derived.evidence_id
    assert restored.read(reloaded.derived) == b"offline\nreplay\n"
    verify_derivation(restored, reloaded)


def test_semantic_identity_survives_source_reencryption_identity_boundary(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"same semantic source\n",
        source_ref="slot-a",
        media_type="text/plain",
    )
    renamed = store.import_bytes(
        b"same semantic source\n",
        source_ref="slot-b",
        media_type="text/plain",
    )

    first = derive_utf8_text(store, source)
    second = derive_utf8_text(store, renamed)

    assert source.evidence_id == renamed.evidence_id
    assert source.manifest_digest != renamed.manifest_digest
    assert first.semantic_derivation_id == second.semantic_derivation_id
    assert first.derived.evidence_id == second.derived.evidence_id


def test_invalid_utf8_wrong_media_bom_nul_and_budget_fail_closed(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    invalid_utf8 = store.import_bytes(
        b"\xff\xfe",
        source_ref="invalid-utf8",
        media_type="text/plain",
    )
    wrong_media = store.import_bytes(
        b"valid utf8",
        source_ref="wrong-media",
        media_type="application/octet-stream",
    )
    bom = store.import_bytes(
        b"\xef\xbb\xbftext",
        source_ref="bom",
        media_type="text/plain",
    )
    nul = store.import_bytes(
        b"a\x00b",
        source_ref="nul",
        media_type="text/plain",
    )

    with pytest.raises(PrivateEvidenceError, match="strict UTF-8"):
        derive_utf8_text(store, invalid_utf8)
    with pytest.raises(PrivateEvidenceError, match="textual source media"):
        derive_utf8_text(store, wrong_media)
    with pytest.raises(PrivateEvidenceError, match="BOM"):
        derive_utf8_text(store, bom)
    with pytest.raises(PrivateEvidenceError, match="NUL"):
        derive_utf8_text(store, nul)
    with pytest.raises(PrivateEvidenceError, match="budget"):
        derive_utf8_text(store, nul, max_input_bytes=MAX_TEXT_INPUT_BYTES + 1)


def test_environment_bound_derivation_requires_and_binds_tool_identity(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"synthetic image bytes",
        source_ref="image-slot",
        media_type="image/png",
    )

    with pytest.raises(PrivateEvidenceError, match="tool identity"):
        record_environment_bound_text_derivation(
            store,
            source,
            "ocr output\n",
            transform_id="synthetic-ocr",
            transform_version=1,
            config={"mode": 6},
            tool_identity="",
        )

    first = record_environment_bound_text_derivation(
        store,
        source,
        "ocr output\n",
        transform_id="synthetic-ocr",
        transform_version=1,
        config={"mode": 6},
        tool_identity="tool-binary-digest:a",
    )
    second = record_environment_bound_text_derivation(
        store,
        source,
        "ocr output\n",
        transform_id="synthetic-ocr",
        transform_version=1,
        config={"mode": 6},
        tool_identity="tool-binary-digest:b",
    )

    assert first.replay_class is ReplayClass.ENVIRONMENT_BOUND
    assert second.replay_class is ReplayClass.ENVIRONMENT_BOUND
    assert first.semantic_derivation_id != second.semantic_derivation_id
    assert first.derived.evidence_id == second.derived.evidence_id


def test_same_derivation_identity_rejects_output_divergence(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"synthetic source",
        source_ref="source",
        media_type="image/png",
    )
    record_environment_bound_text_derivation(
        store,
        source,
        "first output\n",
        transform_id="synthetic-ocr",
        transform_version=1,
        config={"mode": 6},
        tool_identity="same-tool",
    )

    with pytest.raises(PrivateEvidenceError, match="mutation"):
        record_environment_bound_text_derivation(
            store,
            source,
            "different output\n",
            transform_id="synthetic-ocr",
            transform_version=1,
            config={"mode": 6},
            tool_identity="same-tool",
        )


def test_derivation_receipt_tamper_and_unknown_fields_fail_closed(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"receipt-bound\n",
        source_ref="source",
        media_type="text/plain",
    )
    result = derive_utf8_text(store, source)
    receipt = json.loads(result.derivation_receipt_path.read_text(encoding="utf-8"))
    receipt["unexpected"] = True
    result.derivation_receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(PrivateEvidenceError, match="unknown or missing"):
        verify_derivation(store, result)


def test_cross_case_derivation_is_denied_by_existing_case_scope(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    source_store = _store(root)
    source = source_store.import_bytes(
        b"case scoped\n",
        source_ref="source",
        media_type="text/plain",
    )
    other_store = PrivateEvidenceStore(
        root,
        key_provider=KeyProvider(),
        authorization=AuthorizationContext(
            subject_id="synthetic-derivation-worker",
            tenant_id="synthetic-tenant",
            roles=("case-worker",),
            permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
            case_ids=("CASE-DERIVE", "CASE-OTHER"),
        ),
        tenant_id="synthetic-tenant",
        case_id="CASE-OTHER",
        key_id="case-key",
    )

    with pytest.raises(PrivateEvidenceError, match="different case scope"):
        derive_utf8_text(other_store, source)
