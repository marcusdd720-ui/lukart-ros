"""Private local ingestion of real case source documents."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from knowledge.models.case_manifest import CaseManifest

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    document_id: str
    source_name: str
    source_path: Path
    original_path: Path
    extracted_path: Path
    markdown_path: Path
    sha256: str
    document_type: str
    extraction_method: str


class IngestionError(RuntimeError):
    """Raised when a source document cannot be safely ingested."""


def _safe_document_id(index: int, path: Path) -> str:
    stem = "".join(ch if ch.isalnum() else "_" for ch in path.stem).strip("_")
    stem = stem or "document"
    return f"DOC-{index:03d}-{stem}"[:120]


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
            f"Tesseract failed for {source.name}: {result.stderr.strip() or result.returncode}"
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
            raise IngestionError(f"Unsupported text encoding: {source}") from exc
    raise IngestionError(
        f"Unsupported source type '{source.suffix}' for {source.name}. "
        "Supported: images (JPG/JPEG/PNG/TIFF/WEBP) and TXT/MD."
    )


def _write_markdown(
    path: Path,
    *,
    document_id: str,
    title: str,
    sha256: str,
    document_type: str,
    extraction_method: str,
    source_name: str,
    text: str,
) -> None:
    path.write_text(
        "---\n"
        f"id: {document_id}\n"
        f"title: {title}\n"
        f"type: {document_type}\n"
        "version: 1\n"
        "status: ingested\n"
        "---\n\n"
        f"# {title}\n\n"
        f"Source filename: {source_name}\n"
        f"Source SHA256: {sha256}\n"
        f"Extraction method: {extraction_method}\n\n"
        "## Extracted text\n\n"
        f"{text.strip()}\n",
        encoding="utf-8",
    )


def ingest_directory(
    case_dir: Path,
    source_directory: Path,
    *,
    document_type: str = "real_case",
) -> list[IngestedDocument]:
    """Copy source documents into a private case and create deterministic text views."""
    case_path = case_dir.expanduser().resolve()
    source_path = source_directory.expanduser().resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(source_path)
    if case_path == source_path or case_path in source_path.parents:
        raise IngestionError("Source directory cannot be inside the target case directory.")

    original_dir = case_path / "original"
    extracted_dir = case_path / "extracted"
    markdown_dir = case_path / "markdown"
    for directory in (original_dir, extracted_dir, markdown_dir):
        directory.mkdir(parents=True, exist_ok=True)

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
        names = ", ".join(path.name for path in unsupported)
        raise IngestionError(f"Unsupported source file types: {names}")

    results: list[IngestedDocument] = []
    for index, source in enumerate(candidates, start=1):
        document_id = _safe_document_id(index, source)
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        original_path = original_dir / source.name
        if original_path.exists() and original_path.read_bytes() != payload:
            original_path = original_dir / f"{document_id}{source.suffix.lower()}"
        original_path.write_bytes(payload)

        text, source_kind, extraction_method = _extract_text(source)
        extracted_path = extracted_dir / f"{document_id}.txt"
        extracted_path.write_text(text, encoding="utf-8")
        markdown_path = markdown_dir / f"{document_id}.md"
        _write_markdown(
            markdown_path,
            document_id=document_id,
            title=source.name,
            sha256=digest,
            document_type=document_type,
            extraction_method=extraction_method,
            source_name=source.name,
            text=text,
        )
        results.append(
            IngestedDocument(
                document_id=document_id,
                source_name=source.name,
                source_path=source,
                original_path=original_path.resolve(),
                extracted_path=extracted_path.resolve(),
                markdown_path=markdown_path.resolve(),
                sha256=digest,
                document_type=document_type,
                extraction_method=f"{source_kind}:{extraction_method}",
            )
        )

    inventory = [
        {
            "document_id": item.document_id,
            "source_name": item.source_name,
            "original_path": str(item.original_path),
            "extracted_path": str(item.extracted_path),
            "markdown_path": str(item.markdown_path),
            "sha256": item.sha256,
            "document_type": item.document_type,
            "extraction_method": item.extraction_method,
        }
        for item in results
    ]
    (case_path / "document_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_path = case_path / "case_manifest.json"
    existing = (
        CaseManifest.load(case_path)
        if manifest_path.is_file()
        else CaseManifest(case_key=case_path.name, case_id=case_path.name)
    )
    CaseManifest(
        case_key=existing.case_key,
        case_id=existing.case_id,
        lifecycle_state=existing.lifecycle_state,
        version=existing.version,
        document_ids=tuple(item.document_id for item in results),
    ).save(case_path)
    return results
