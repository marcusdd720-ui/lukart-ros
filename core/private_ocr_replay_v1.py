"""Observed replay verification for CASE-OPS-07 environment-bound OCR derivations."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import core.case_ingestion as case_ingestion
from core.private_evidence_derivation_v1 import ReplayClass, load_derivation
from core.private_evidence_v1 import (
    PrivateEvidenceError,
    PrivateEvidenceStore,
    canonical_json,
    content_id,
    digest_hex,
    digest_object,
    opaque_digest,
)

OCR_REPLAY_SCHEMA_V1 = "lukart.environment-bound-ocr-replay-proof.v1"
OCR_TRANSFORM_ID_V1 = "lukart.tesseract-ocr-pol-eng-psm6"
OCR_TRANSFORM_VERSION_V1 = 1
OCR_CONFIG_V1: dict[str, object] = {
    "language": "pol+eng",
    "psm": 6,
    "transport": "stdin",
}
MAX_OCR_REPLAY_SOURCE_BYTES = 64 * 1024 * 1024
MAX_OCR_REPLAY_OUTPUT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class EnvironmentBoundOcrReplayProofV1:
    """Digest-only proof that one recorded OCR output was observed again."""

    schema: str
    status: str
    replay_class: str
    case_scope_digest: str
    derivation_receipt_digest: str
    semantic_derivation_id: str
    source_evidence_id: str
    derived_evidence_id: str
    transform_id: str
    transform_version: int
    config_digest: str
    tool_identity_digest: str
    observed_output_id: str

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def proof_id(self) -> str:
        return digest_object(self.canonical_dict())


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


def _required_digest(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise PrivateEvidenceError(f"invalid OCR replay receipt field: {key}")
    digest_hex(value)
    return value


def _current_tesseract_identity() -> str:
    executable_name = shutil.which("tesseract")
    if not executable_name:
        raise PrivateEvidenceError("OCR replay requires the local 'tesseract' executable")
    executable = Path(executable_name).resolve()
    try:
        return case_ingestion._tesseract_identity(executable)
    except case_ingestion.IngestionError as exc:
        raise PrivateEvidenceError("cannot establish current OCR tool identity") from exc


def verify_environment_bound_ocr_replay(
    store: PrivateEvidenceStore,
    derivation_receipt_digest: str,
    *,
    max_source_bytes: int = MAX_OCR_REPLAY_SOURCE_BYTES,
    max_output_bytes: int = MAX_OCR_REPLAY_OUTPUT_BYTES,
) -> EnvironmentBoundOcrReplayProofV1:
    """Replay one exact Tesseract v1 derivation without upgrading its replay class."""
    if max_source_bytes < 1 or max_source_bytes > MAX_OCR_REPLAY_SOURCE_BYTES:
        raise PrivateEvidenceError("OCR replay source budget is invalid")
    if max_output_bytes < 1 or max_output_bytes > MAX_OCR_REPLAY_OUTPUT_BYTES:
        raise PrivateEvidenceError("OCR replay output budget is invalid")

    derivation = load_derivation(store, derivation_receipt_digest)
    receipt = _load_mapping(derivation.derivation_receipt_path, label="derivation receipt")
    if digest_object(receipt) != derivation_receipt_digest:
        raise PrivateEvidenceError("derivation receipt changed during OCR replay verification")
    if derivation.replay_class is not ReplayClass.ENVIRONMENT_BOUND:
        raise PrivateEvidenceError("OCR replay requires an ENVIRONMENT_BOUND derivation")
    if receipt.get("transform_id") != OCR_TRANSFORM_ID_V1:
        raise PrivateEvidenceError("unsupported OCR replay transform")
    transform_version = receipt.get("transform_version")
    if (
        isinstance(transform_version, bool)
        or not isinstance(transform_version, int)
        or transform_version != OCR_TRANSFORM_VERSION_V1
    ):
        raise PrivateEvidenceError("unsupported OCR replay transform version")
    expected_config_digest = digest_object(OCR_CONFIG_V1)
    if receipt.get("config_digest") != expected_config_digest:
        raise PrivateEvidenceError("unsupported OCR replay configuration")
    recorded_tool_digest = _required_digest(receipt, "tool_identity_digest")

    source_manifest = _load_mapping(derivation.source.manifest_path, label="source manifest")
    media_type = source_manifest.get("media_type")
    if not isinstance(media_type, str) or not media_type.startswith("image/"):
        raise PrivateEvidenceError("OCR replay requires image source evidence")
    size_bytes = source_manifest.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise PrivateEvidenceError("invalid OCR replay source size")
    if size_bytes > max_source_bytes:
        raise PrivateEvidenceError("OCR replay source budget exceeded")

    before_identity = _current_tesseract_identity()
    if opaque_digest(before_identity) != recorded_tool_digest:
        raise PrivateEvidenceError("OCR replay environment drift detected")

    source_payload = store.read(derivation.source)
    if len(source_payload) != size_bytes:
        raise PrivateEvidenceError("OCR replay source size changed")
    try:
        observed_text, execution_identity = case_ingestion._run_tesseract(source_payload)
    except case_ingestion.IngestionError as exc:
        raise PrivateEvidenceError("OCR replay execution failed") from exc
    if opaque_digest(execution_identity) != recorded_tool_digest:
        raise PrivateEvidenceError("OCR replay tool identity changed during execution")

    observed_output = observed_text.encode("utf-8")
    if len(observed_output) > max_output_bytes:
        raise PrivateEvidenceError("OCR replay output budget exceeded")
    recorded_output = store.read(derivation.derived)
    if observed_output != recorded_output:
        raise PrivateEvidenceError("OCR replay output mismatch")
    observed_output_id = content_id(observed_output)
    if observed_output_id != derivation.derived.evidence_id:
        raise PrivateEvidenceError("OCR replay output identity mismatch")

    return EnvironmentBoundOcrReplayProofV1(
        schema=OCR_REPLAY_SCHEMA_V1,
        status="MATCH",
        replay_class=ReplayClass.ENVIRONMENT_BOUND.value,
        case_scope_digest=store.case_scope_digest,
        derivation_receipt_digest=derivation.derivation_receipt_digest,
        semantic_derivation_id=derivation.semantic_derivation_id,
        source_evidence_id=derivation.source.evidence_id,
        derived_evidence_id=derivation.derived.evidence_id,
        transform_id=OCR_TRANSFORM_ID_V1,
        transform_version=OCR_TRANSFORM_VERSION_V1,
        config_digest=expected_config_digest,
        tool_identity_digest=recorded_tool_digest,
        observed_output_id=observed_output_id,
    )


def write_ocr_replay_proof(
    proof: EnvironmentBoundOcrReplayProofV1,
    target: Path,
    *,
    repo_root: Path,
) -> Path:
    """Write one immutable digest-only proof outside the public repository."""
    absolute = Path(os.path.abspath(target.expanduser()))
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and candidate.is_symlink():
            raise PrivateEvidenceError("OCR replay proof path must not traverse symlinks")
    resolved_repo = repo_root.resolve()
    resolved_target = absolute.resolve()
    if resolved_target == resolved_repo or resolved_repo in resolved_target.parents:
        raise PrivateEvidenceError("OCR replay proof must be outside the public repository")

    payload = canonical_json(proof.canonical_dict()) + b"\n"
    resolved_target.parent.mkdir(parents=True, exist_ok=True)
    if resolved_target.parent.is_symlink():
        raise PrivateEvidenceError("OCR replay proof parent must not be a symlink")
    try:
        fd = os.open(resolved_target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if resolved_target.is_symlink() or resolved_target.read_bytes() != payload:
            raise PrivateEvidenceError("immutable OCR replay proof divergence detected") from None
        return resolved_target
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        resolved_target.unlink(missing_ok=True)
        raise
    return resolved_target
