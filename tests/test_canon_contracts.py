from pathlib import Path

from validation.canon_contracts import parse_canon_document, validate_canon_directory


def _write_canon(
    root: Path,
    canonical_id: str,
    *,
    depends_on: str = "none",
    status: str = "CANDIDATE CANON",
) -> Path:
    path = root / f"{canonical_id}.md"
    path.write_text(
        "\n".join(
            [
                f"# {canonical_id} — Test Canon",
                "",
                f"Canonical ID: {canonical_id}",
                "Title: Test Canon",
                "Version: 1.0",
                f"Status: {status}",
                "Class: ARCHITECTURE",
                "Stability Index: 3",
                "Owner: Test Architecture",
                f"Depends On: {depends_on}",
                "Affects: tests",
                "Supersedes: none",
                "Validation Method: tests",
                "Review Requirement: independent review before CANONICAL",
                "Change Policy: versioned semantic change only",
                "",
                "## 1. Purpose",
                "Test fixture.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_current_canon_directory_is_structurally_valid() -> None:
    violations = validate_canon_directory(Path("canon"))
    assert violations == ()


def test_missing_metadata_fails(tmp_path: Path) -> None:
    path = _write_canon(tmp_path, "KZZ-1.0")
    text = path.read_text(encoding="utf-8").replace("Owner: Test Architecture\n", "")
    path.write_text(text, encoding="utf-8")

    _, violations = parse_canon_document(path)

    assert any(item.code == "MISSING_METADATA" and "Owner" in item.message for item in violations)


def test_missing_internal_dependency_fails(tmp_path: Path) -> None:
    _write_canon(tmp_path, "KAA-1.0", depends_on="KBB-1.0")

    violations = validate_canon_directory(tmp_path)

    assert any(item.code == "MISSING_CANON_DEPENDENCY" for item in violations)


def test_external_dependency_is_allowed(tmp_path: Path) -> None:
    _write_canon(tmp_path, "KAA-1.0", depends_on="FOUNDATION.md; accepted ADRs")

    assert validate_canon_directory(tmp_path) == ()


def test_dependency_cycle_fails(tmp_path: Path) -> None:
    _write_canon(tmp_path, "KAA-1.0", depends_on="KBB-1.0")
    _write_canon(tmp_path, "KBB-1.0", depends_on="KAA-1.0")

    violations = validate_canon_directory(tmp_path)

    assert any(item.code == "DEPENDENCY_CYCLE" for item in violations)


def test_invalid_status_fails(tmp_path: Path) -> None:
    _write_canon(tmp_path, "KAA-1.0", status="READY")

    violations = validate_canon_directory(tmp_path)

    assert any(item.code == "INVALID_STATUS" for item in violations)
