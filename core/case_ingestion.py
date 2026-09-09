"""Private fail-closed ingestion of real case source documents."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext
from core.local_case_store import validate_untrusted_path
from core.private_evidence_derivation_v1 import (
    ReplayClass,
    derive_utf8_text,
    record_environment_bound_text_derivation,
)
from core.private_evidence_v1 import (
    EvidenceKeyProvider,
    EvidenceKind,
    PrivateEvidenceError,
    PrivateEvidenceStore,
    opaque_digest,
    sha256_hex,
)
from knowledge.models.case_manifest import CaseManifest

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}
_TESSERACT_CONFIG = {"language": "pol+eng", "psm": 6, "transport": "stdin"}


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    document_id: str
    evidence_id: str
    manifest_digest: str
    receipt_digest: str
    encrypted_path: Path
    extracted_evidence_id: str
    extracted_manifest_digest: str
    extracted_receipt_digest: str
    derivation_identity: str
    derivation_receipt_digest: str
    derivation_replay_class: str
    sha256: str
    document_type: str
    extraction_method: str


class IngestionError(RuntimeError):
    """Raised when a source document cannot be safely ingested."""


def _safe_document_id(index: int) -> str:
    return f"DOC-{index:03d}"


def _tesseract_identity(executable: Path) -> str:
    try:
        binary_digest = sha256_hex(executable.read_bytes())
        version = subprocess.run(
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise IngestionError("Cannot establish local Tesseract identity") from exc
    if version.returncode != 0:
        raise IngestionError("Cannot establish local Tesseract identity")
    version_digest = sha256_hex(version.stdout + b"\n" + version.stderr)
    return f"tesseract-binary:{binary_digest}|version-output:{version_digest}"


def _run_tesseract(payload: bytes) -> tuple[str, str]:
    executable_name = shutil.which("tesseract")
    if not executable_name:
        raise IngestionError("Image ingestion requires the 'tesseract' executable on PATH.")
    executable = Path(executable_name).resolve()
    tool_identity = _tesseract_identity(executable)
    try:
        result = subprocess.run(
            [str(executable), "stdin", "stdout", "-l", "pol+eng", "--psm", "6"],
            input=payload,
            check=False,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise IngestionError("Tesseract execution failed") from exc
    if result.returncode != 0:
        raise IngestionError(f"Tesseract failed with return code {result.returncode}")
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestionError("Tesseract output is not strict UTF-8") from exc
    return text.replace("\x0c", "").strip() + "\n", tool_identity


def ingest_directory(
    case_dir: Path,
    source_directory: Path,
    *,
    authorization: AuthorizationContext | None = None,
    key_provider: EvidenceKeyProvider | None = None,
    tenant_id: str | None = None,
    key_id: str | None = None,
    key_version: int = 1,
    document_type: str = "real_case",
) -> list[IngestedDocument]:
    """Encrypt source and provenance-bound text views; persist no plaintext evidence."""
    if authorization is None or key_provider is None or not tenant_id or not key_id:
        raise IngestionError(
            "private ingestion requires authorization, key provider, tenant id and key id"
        )
    try:
        case_path = validate_untrusted_path(case_dir, label="case directory").resolve()
        source_path = validate_untrusted_path(
            source_directory, label="source directory"
        ).resolve()
    except RuntimeError as exc:
        raise IngestionError(str(exc)) from exc
    if not source_path.is_dir():
        raise FileNotFoundError(source_path)
    if case_path == source_path or case_path in source_path.parents:
        raise IngestionError("Source directory cannot be inside the target case directory.")
    case_path.mkdir(parents=True, exist_ok=True)

    manifest_path = case_path / "case_manifest.json"
    existing = (
        CaseManifest.load(case_path)
        if manifest_path.is_file()
        else CaseManifest(case_key=case_path.name, case_id=case_path.name)
    )
    try:
        store = PrivateEvidenceStore(
            case_path / ".private-evidence",
            key_provider=key_provider,
            authorization=authorization,
            tenant_id=tenant_id,
            case_id=existing.case_id,
            key_id=key_id,
            key_version=key_version,
        )
    except PrivateEvidenceError as exc:
        raise IngestionError(str(exc)) from exc

    candidates = [
        path
        for path in sorted(source_path.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]
    if not candidates:
        raise IngestionError(f"No source files found in {source_path}")
    unsupported = [
        path
        for path in candidates
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES | SUPPORTED_TEXT_SUFFIXES
    ]
    if unsupported:
        raise IngestionError("Unsupported source file types are present")

    results: list[IngestedDocument] = []
    inventory: list[dict[str, object]] = []
    for index, source in enumerate(candidates, start=1):
        document_id = _safe_document_id(index)
        try:
            original = store.import_file(
                source,
                source_ref=f"document-slot:{index}",
                kind=EvidenceKind.PRIMARY,
            )
            suffix = source.suffix.lower()
            if suffix in SUPPORTED_TEXT_SUFFIXES:
                derivation = derive_utf8_text(store, original)
                source_kind = "text"
                extraction_method = "utf8-lf-text-view-v1"
            else:
                source_payload = store.read(original)
                text, tool_identity = _run_tesseract(source_payload)
                derivation = record_environment_bound_text_derivation(
                    store,
                    original,
                    text,
                    transform_id="lukart.tesseract-ocr-pol-eng-psm6",
                    transform_version=1,
                    config=dict(_TESSERACT_CONFIG),
                    tool_identity=tool_identity,
                )
                source_kind = "image"
                extraction_method = "tesseract-pol+eng-psm6"
        except PrivateEvidenceError as exc:
            raise IngestionError(str(exc)) from exc

        extracted = derivation.derived
        sha256 = original.evidence_id.removeprefix("sha256:")
        method = f"{source_kind}:{extraction_method}"
        item = IngestedDocument(
            document_id=document_id,
            evidence_id=original.evidence_id,
            manifest_digest=original.manifest_digest,
            receipt_digest=original.receipt_digest,
            encrypted_path=original.envelope_path.resolve(),
            extracted_evidence_id=extracted.evidence_id,
            extracted_manifest_digest=extracted.manifest_digest,
            extracted_receipt_digest=extracted.receipt_digest,
            derivation_identity=derivation.semantic_derivation_id,
            derivation_receipt_digest=derivation.derivation_receipt_digest,
            derivation_replay_class=derivation.replay_class.value,
            sha256=sha256,
            document_type=document_type,
            extraction_method=method,
        )
        results.append(item)
        inventory.append(
            {
                "document_id": document_id,
                "evidence_id": original.evidence_id,
                "manifest_digest": original.manifest_digest,
                "receipt_digest": original.receipt_digest,
                "extracted_evidence_id": extracted.evidence_id,
                "extracted_manifest_digest": extracted.manifest_digest,
                "extracted_receipt_digest": extracted.receipt_digest,
                "derivation_identity": derivation.semantic_derivation_id,
                "derivation_receipt_digest": derivation.derivation_receipt_digest,
                "derivation_replay_class": derivation.replay_class.value,
                "source_name_digest": opaque_digest(source.name),
                "sha256": sha256,
                "document_type": document_type,
                "extraction_method": method,
                "local_only": True,
            }
        )
        if derivation.replay_class not in {
            ReplayClass.DETERMINISTIC,
            ReplayClass.ENVIRONMENT_BOUND,
        }:
            raise IngestionError("unsupported derivation replay class")

    (case_path / "document_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    CaseManifest(
        case_key=existing.case_key,
        case_id=existing.case_id,
        lifecycle_state=existing.lifecycle_state,
        version=existing.version,
        document_ids=tuple(item.document_id for item in results),
    ).save(case_path)
    return results
