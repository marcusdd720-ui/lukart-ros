from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.architectural_audit import (
    STATUSES,
    AuditContext,
    build_items,
    current_sha,
    write_reports,
)


def test_audit_has_exactly_25_items(repository_root: Path) -> None:
    items = build_items(AuditContext(repository_root))
    assert len(items) == 25
    assert [item.id for item in items] == [f"A{i}" for i in range(1, 26)]
    assert all(item.status in STATUSES for item in items)


def test_audit_context_blocks_path_escape(repository_root: Path) -> None:
    context = AuditContext(repository_root)
    with pytest.raises(ValueError):
        context.path("../outside")


def test_current_sha_prefers_github_sha(
    monkeypatch: pytest.MonkeyPatch, repository_root: Path
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    assert current_sha(repository_root) == "abc123"


def test_reports_are_written_outside_repository(
    tmp_path: Path, repository_root: Path
) -> None:
    output = tmp_path / "audit"
    items = build_items(AuditContext(repository_root))
    write_reports(output, "test-sha", items)

    payload = json.loads((output / "audit-report.json").read_text(encoding="utf-8"))
    assert payload["commit_sha"] == "test-sha"
    assert len(payload["items"]) == 25
    assert (output / "audit-report.md").exists()
    assert repository_root not in output.parents


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]
