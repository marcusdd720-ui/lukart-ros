"""Local provenance-bound evidence derivation for CASE-OPS-02."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from core.private_evidence_v1 import (
    EvidenceKind,
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceStore,
    canonical_json,
    digest_hex,
    digest_object,
    opaque_digest,
)

SCHEMA_DERIVATION_SPEC = "lukart.local-evidence-derivation-spec.v1"
SCHEMA_DERIVATION_RECEIPT = "lukart.local-evidence-derivation-receipt.v1"
UTF8_TEXT_TRANSFORM = "lukart.utf8-lf-text-view"
UTF8_TEXT_TRANSFORM_VERSION = 1
MAX_TEXT_INPUT_BYTES = 16 * 1024 * 1024


class ReplayClass(StrEnum):
    """How strongly a derivation can be replayed from its bound identity."""

    DETERMINISTIC = "DETERMINISTIC"
    ENVIRONMENT_BOUND = "ENVIRONMENT_BOUND"


@dataclass(frozen=True, slots=True)
class LocalDerivationReceiptV1:
    """Immutable provenance edge from exact source evidence to exact derived evidence."""

    schema: str
    case_scope_digest: str
    semantic_derivation_id: str
    source_evidence_id: str
    source_manifest_digest: str
    source_receipt_digest: str
    derived_evidence_id: str
    derived_manifest_digest: str
    derived_receipt_digest: str
    transform_id: str
    transform_version: int
    config_digest: str
    replay_class: str
    tool_identity_digest: str | None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DerivedEvidence:
    """Exact source, derived evidence and provenance receipt identities."""

    source: ImportedEvidence
    derived: ImportedEvidence
    semantic_derivation_id: str
    derivation_receipt_digest: str
    derivation_receipt_path: Path
    replay_class: ReplayClass


_RECEIPT_FIELDS = frozenset(LocalDerivationReceiptV1.__dataclass_fields__)


def _load_mapping(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateEvidenceError(f"{label} missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceError(f"{label} must be a mapping")
    return value


def _exclusive_json(path: Path, value: object) -> None:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PrivateEvidenceError("derivation receipt path contains a symlink")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != payload:
            raise PrivateEvidenceError("immutable derivation receipt divergence detected") from None
        return
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _receipt_path(store: PrivateEvidenceStore, digest: str) -> Path:
    value = digest_hex(digest)
    base = store.root / "derivations"
    target = base / value[:2] / f"{value}.json"
    if base.is_symlink() or target.parent.is_symlink():
        raise PrivateEvidenceError("derivation receipt path contains a symlink")
    return target


def _required_digest_field(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise PrivateEvidenceError(f"invalid derivation receipt field: {key}")
    digest_hex(value)
    return value


def _replay_class(value: object) -> ReplayClass:
    if not isinstance(value, str):
        raise PrivateEvidenceError("invalid derivation replay class")
    try:
        return ReplayClass(value)
    except ValueError as exc:
        raise PrivateEvidenceError("unsupported derivation replay class") from exc


def _manifest(store: PrivateEvidenceStore, source: ImportedEvidence) -> dict[str, object]:
    store.verify(source)
    manifest = _load_mapping(source.manifest_path, label="source manifest")
    if digest_object(manifest) != source.manifest_digest:
        raise PrivateEvidenceError("source manifest digest mismatch")
    if manifest.get("evidence_id") != source.evidence_id:
        raise PrivateEvidenceError("source evidence identity mismatch")
    if manifest.get("case_scope_digest") != store.case_scope_digest:
        raise PrivateEvidenceError("source belongs to a different case scope")
    return manifest


def _config_digest(config: dict[str, object]) -> str:
    try:
        return digest_object(config)
    except (TypeError, ValueError) as exc:
        raise PrivateEvidenceError("derivation config must be canonical JSON") from exc


def _semantic_derivation_id(
    *,
    source_evidence_id: str,
    transform_id: str,
    transform_version: int,
    config_digest: str,
    replay_class: ReplayClass,
    tool_identity_digest: str | None,
) -> str:
    return digest_object(
        {
            "schema": SCHEMA_DERIVATION_SPEC,
            "source_evidence_id": source_evidence_id,
            "transform_id": transform_id,
            "transform_version": transform_version,
            "config_digest": config_digest,
            "replay_class": replay_class.value,
            "tool_identity_digest": tool_identity_digest,
        }
    )


def _persist_derivation(
    store: PrivateEvidenceStore,
    source: ImportedEvidence,
    output: bytes,
    *,
    transform_id: str,
    transform_version: int,
    config: dict[str, object],
    replay_class: ReplayClass,
    tool_identity: str | None,
) -> DerivedEvidence:
    transform = transform_id.strip()
    if not transform or transform_version < 1:
        raise PrivateEvidenceError("transform id and positive version are required")
    _manifest(store, source)
    config_digest = _config_digest(config)
    if replay_class is ReplayClass.ENVIRONMENT_BOUND:
        if tool_identity is None or not tool_identity.strip():
            raise PrivateEvidenceError("environment-bound derivation requires tool identity")
        tool_identity_digest: str | None = opaque_digest(tool_identity)
    else:
        if tool_identity is not None:
            raise PrivateEvidenceError("deterministic derivation cannot carry tool identity")
        tool_identity_digest = None

    semantic_id = _semantic_derivation_id(
        source_evidence_id=source.evidence_id,
        transform_id=transform,
        transform_version=transform_version,
        config_digest=config_digest,
        replay_class=replay_class,
        tool_identity_digest=tool_identity_digest,
    )
    derived = store.import_bytes(
        output,
        source_ref=f"derivation:{semantic_id}",
        kind=EvidenceKind.DERIVED,
        media_type="text/plain",
    )
    receipt = LocalDerivationReceiptV1(
        schema=SCHEMA_DERIVATION_RECEIPT,
        case_scope_digest=store.case_scope_digest,
        semantic_derivation_id=semantic_id,
        source_evidence_id=source.evidence_id,
        source_manifest_digest=source.manifest_digest,
        source_receipt_digest=source.receipt_digest,
        derived_evidence_id=derived.evidence_id,
        derived_manifest_digest=derived.manifest_digest,
        derived_receipt_digest=derived.receipt_digest,
        transform_id=transform,
        transform_version=transform_version,
        config_digest=config_digest,
        replay_class=replay_class.value,
        tool_identity_digest=tool_identity_digest,
    )
    receipt_dict = receipt.canonical_dict()
    receipt_digest = digest_object(receipt_dict)
    receipt_path = _receipt_path(store, receipt_digest)
    _exclusive_json(receipt_path, receipt_dict)
    result = DerivedEvidence(
        source=source,
        derived=derived,
        semantic_derivation_id=semantic_id,
        derivation_receipt_digest=receipt_digest,
        derivation_receipt_path=receipt_path,
        replay_class=replay_class,
    )
    verify_derivation(store, result)
    return result


def derive_utf8_text(
    store: PrivateEvidenceStore,
    source: ImportedEvidence,
    *,
    max_input_bytes: int = MAX_TEXT_INPUT_BYTES,
) -> DerivedEvidence:
    """Create a deterministic LF-normalized UTF-8 text view from exact evidence bytes."""
    if max_input_bytes < 1 or max_input_bytes > MAX_TEXT_INPUT_BYTES:
        raise PrivateEvidenceError("text derivation input budget is invalid")
    manifest = _manifest(store, source)
    media_type = manifest.get("media_type")
    if media_type not in {"text/plain", "text/markdown"}:
        raise PrivateEvidenceError("deterministic text derivation requires textual source media")
    payload = store.read(source)
    if len(payload) > max_input_bytes:
        raise PrivateEvidenceError("text derivation input budget exceeded")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PrivateEvidenceError("text derivation requires strict UTF-8") from exc
    if text.startswith("\ufeff"):
        raise PrivateEvidenceError("UTF-8 BOM is not accepted by text derivation v1")
    if "\x00" in text:
        raise PrivateEvidenceError("NUL is not accepted by text derivation v1")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return _persist_derivation(
        store,
        source,
        normalized,
        transform_id=UTF8_TEXT_TRANSFORM,
        transform_version=UTF8_TEXT_TRANSFORM_VERSION,
        config={
            "encoding": "utf-8-strict",
            "newline": "LF",
            "bom": "reject",
            "nul": "reject",
            "max_input_bytes": max_input_bytes,
        },
        replay_class=ReplayClass.DETERMINISTIC,
        tool_identity=None,
    )


def record_environment_bound_text_derivation(
    store: PrivateEvidenceStore,
    source: ImportedEvidence,
    output_text: str,
    *,
    transform_id: str,
    transform_version: int,
    config: dict[str, object],
    tool_identity: str,
    max_output_bytes: int = MAX_TEXT_INPUT_BYTES,
) -> DerivedEvidence:
    """Bind local external-tool output without claiming environment-independent replay."""
    if max_output_bytes < 1 or max_output_bytes > MAX_TEXT_INPUT_BYTES:
        raise PrivateEvidenceError("environment-bound output budget is invalid")
    if not isinstance(output_text, str):
        raise PrivateEvidenceError("environment-bound text output must be a string")
    if "\x00" in output_text:
        raise PrivateEvidenceError("NUL is not accepted in derived text")
    output = output_text.encode("utf-8")
    if len(output) > max_output_bytes:
        raise PrivateEvidenceError("environment-bound output budget exceeded")
    return _persist_derivation(
        store,
        source,
        output,
        transform_id=transform_id,
        transform_version=transform_version,
        config=config,
        replay_class=ReplayClass.ENVIRONMENT_BOUND,
        tool_identity=tool_identity,
    )


def load_derivation(
    store: PrivateEvidenceStore,
    derivation_receipt_digest: str,
) -> DerivedEvidence:
    """Rehydrate and verify one derivation from its content-addressed receipt only."""
    receipt_path = _receipt_path(store, derivation_receipt_digest)
    receipt = _load_mapping(receipt_path, label="derivation receipt")
    if set(receipt) != _RECEIPT_FIELDS:
        raise PrivateEvidenceError("unknown or missing derivation receipt fields")
    if digest_object(receipt) != derivation_receipt_digest:
        raise PrivateEvidenceError("derivation receipt digest mismatch")
    if receipt.get("schema") != SCHEMA_DERIVATION_RECEIPT:
        raise PrivateEvidenceError("unsupported derivation receipt schema")

    source_evidence_id = _required_digest_field(receipt, "source_evidence_id")
    source_manifest_digest = _required_digest_field(receipt, "source_manifest_digest")
    source_receipt_digest = _required_digest_field(receipt, "source_receipt_digest")
    derived_evidence_id = _required_digest_field(receipt, "derived_evidence_id")
    derived_manifest_digest = _required_digest_field(receipt, "derived_manifest_digest")
    derived_receipt_digest = _required_digest_field(receipt, "derived_receipt_digest")
    semantic_derivation_id = _required_digest_field(receipt, "semantic_derivation_id")
    replay_class = _replay_class(receipt.get("replay_class"))

    source = store._load_imported(
        evidence_id=source_evidence_id,
        manifest_digest=source_manifest_digest,
        receipt_digest=source_receipt_digest,
    )
    derived = store._load_imported(
        evidence_id=derived_evidence_id,
        manifest_digest=derived_manifest_digest,
        receipt_digest=derived_receipt_digest,
    )
    result = DerivedEvidence(
        source=source,
        derived=derived,
        semantic_derivation_id=semantic_derivation_id,
        derivation_receipt_digest=derivation_receipt_digest,
        derivation_receipt_path=receipt_path,
        replay_class=replay_class,
    )
    verify_derivation(store, result)
    return result


def verify_derivation(store: PrivateEvidenceStore, result: DerivedEvidence) -> None:
    """Verify receipt, source/derived evidence and semantic derivation identity offline."""
    store.verify(result.source)
    store.verify(result.derived)
    receipt = _load_mapping(result.derivation_receipt_path, label="derivation receipt")
    if set(receipt) != _RECEIPT_FIELDS:
        raise PrivateEvidenceError("unknown or missing derivation receipt fields")
    if digest_object(receipt) != result.derivation_receipt_digest:
        raise PrivateEvidenceError("derivation receipt digest mismatch")
    if receipt.get("schema") != SCHEMA_DERIVATION_RECEIPT:
        raise PrivateEvidenceError("unsupported derivation receipt schema")
    expected_bindings = {
        "case_scope_digest": store.case_scope_digest,
        "source_evidence_id": result.source.evidence_id,
        "source_manifest_digest": result.source.manifest_digest,
        "source_receipt_digest": result.source.receipt_digest,
        "derived_evidence_id": result.derived.evidence_id,
        "derived_manifest_digest": result.derived.manifest_digest,
        "derived_receipt_digest": result.derived.receipt_digest,
        "replay_class": result.replay_class.value,
    }
    for key, expected in expected_bindings.items():
        if receipt.get(key) != expected:
            raise PrivateEvidenceError(f"derivation receipt binding mismatch: {key}")

    transform_id = receipt.get("transform_id")
    transform_version = receipt.get("transform_version")
    config_digest = receipt.get("config_digest")
    tool_identity_digest = receipt.get("tool_identity_digest")
    if not isinstance(transform_id, str) or not transform_id.strip():
        raise PrivateEvidenceError("invalid derivation transform id")
    if isinstance(transform_version, bool) or not isinstance(transform_version, int):
        raise PrivateEvidenceError("invalid derivation transform version")
    if transform_version < 1 or not isinstance(config_digest, str):
        raise PrivateEvidenceError("invalid derivation spec fields")
    digest_hex(config_digest)
    if tool_identity_digest is not None:
        if not isinstance(tool_identity_digest, str):
            raise PrivateEvidenceError("invalid tool identity digest")
        digest_hex(tool_identity_digest)
    replay_class = _replay_class(receipt.get("replay_class"))
    if replay_class is ReplayClass.ENVIRONMENT_BOUND and tool_identity_digest is None:
        raise PrivateEvidenceError("environment-bound receipt is missing tool identity")
    if replay_class is ReplayClass.DETERMINISTIC and tool_identity_digest is not None:
        raise PrivateEvidenceError("deterministic receipt unexpectedly carries tool identity")
    semantic_id = _semantic_derivation_id(
        source_evidence_id=result.source.evidence_id,
        transform_id=transform_id,
        transform_version=transform_version,
        config_digest=config_digest,
        replay_class=replay_class,
        tool_identity_digest=tool_identity_digest,
    )
    if receipt.get("semantic_derivation_id") != semantic_id:
        raise PrivateEvidenceError("semantic derivation identity mismatch")
    if semantic_id != result.semantic_derivation_id:
        raise PrivateEvidenceError("derivation result identity mismatch")
