"""Private fail-closed ingestion of real case source documents."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext
from core.private_evidence_v1 import (
    EvidenceKeyProvider,
    EvidenceKind,
    PrivateEvidenceError,
    PrivateEvidenceStore,
    opaque_digest,
)
from knowledge.models.case_manifest import CaseManifest

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    document_id: str
    evidence_id: str
    manifest_digest: str
    receipt_digest: str
    encrypted_path: Path
    extracted_evidence_id: str
    extracted_receipt_digest: str
    sha256: str
    document_type: str
    extraction_method: str


class IngestionError(RuntimeError):
    """Raised when a source document cannot be safely ingested."""


def _safe_document_id(index: int) -> str:
    return f"DOC-{index:03d}"


def _run_tesseract(source: Path) -> str:
    try:
        result = subprocess.run(
            ["tesseract", str(source), "stdout", "-l", "pol+eng", "--psm", "6"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise IngestionError(
            "Image ingestion requires the 'tesseract' executable on PATH."
        ) from exc
    if result.returncode != 0:
        raise IngestionError(
            f"Tesseract failed with return code {result.returncode}"
        )
    return result.stdout.replace("\x0c", "").strip() + "\n"


def _extract_text(source: Path) -> tuple[str, str, str]:
    suffix = source.suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return _run_tesseract(source), "image", "tesseract-pol+eng-psm6"
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        try:
            return source.read_text(encoding="utf-8"), "text", "direct-text"
        except UnicodeDecodeError as exc:
            raise IngestionError("Unsupported text encoding") from exc
    raise IngestionError(f"Unsupported source type: {source.suffix}")


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
    """Encrypt source and derived text; persist no plaintext document artifacts."""
    if authorization is None or key_provider is None or not tenant_id or not key_id:
        raise IngestionError(
            "private ingestion requires authorization, key provider, tenant id and key id"
        )
    case_path = case_dir.expanduser().resolve()
    source_path = source_directory.expanduser().resolve()
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
        text, source_kind, extraction_method = _extract_text(source)
        try:
            original = store.import_file(
                source,
                source_ref=f"document-slot:{index}",
                kind=EvidenceKind.PRIMARY,
            )
            extracted = store.import_bytes(
                text.encode("utf-8"),
                source_ref=f"derived-text:{original.evidence_id}",
                kind=EvidenceKind.DERIVED,
                media_type="text/plain",
            )
        except PrivateEvidenceError as exc:
            raise IngestionError(str(exc)) from exc
        sha256 = original.evidence_id.removeprefix("sha256:")
        method = f"{source_kind}:{extraction_method}"
        item = IngestedDocument(
            document_id=document_id,
            evidence_id=original.evidence_id,
            manifest_digest=original.manifest_digest,
            receipt_digest=original.receipt_digest,
            encrypted_path=original.envelope_path.resolve(),
            extracted_evidence_id=extracted.evidence_id,
            extracted_receipt_digest=extracted.receipt_digest,
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
                "extracted_receipt_digest": extracted.receipt_digest,
                "source_name_digest": opaque_digest(source.name),
                "sha256": sha256,
                "document_type": document_type,
                "extraction_method": method,
                "local_only": True,
            }
        )

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
