from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

GITATTRIBUTES_PATH = Path(".gitattributes")

CORPUS_MANIFEST_PAIRS = (
    (
        Path("data/quality/extraction_gold_v1.json"),
        Path("data/quality/extraction_gold_v1.freeze.json"),
    ),
    (
        Path("data/quality/reasoning_gold_v2.json"),
        Path("data/quality/reasoning_gold_v2.freeze.json"),
    ),
    (
        Path("data/quality/post_v1_gold_v1_1.json"),
        Path("data/quality/post_v1_gold_v1_1.manifest.json"),
    ),
)


def _declared_corpus_sha256(manifest_path: Path) -> str:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = payload.get("corpus_sha256")
    assert isinstance(digest, str)
    return digest


def test_raw_byte_hashed_quality_artifacts_are_lf_pinned() -> None:
    rules = {
        line.strip()
        for line in GITATTRIBUTES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "*.json text eol=lf" in rules


@pytest.mark.parametrize(("corpus_path", "manifest_path"), CORPUS_MANIFEST_PAIRS)
def test_declared_quality_corpus_digest_matches_worktree_bytes(
    corpus_path: Path,
    manifest_path: Path,
) -> None:
    actual = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    expected = _declared_corpus_sha256(manifest_path)

    assert actual == expected
