from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(".")
PRODUCT_SHA = "4ebec450bd87f2c29cc890dbd02941c7af953710"


def _load(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_step16_template_is_bound_to_exact_current_review_package() -> None:
    package_path = "docs/quality/review_packages/step_16_review_package.json"
    template = _load("docs/quality/reviews/step_16_independent_review.template.json")
    package = _load(package_path)

    assert package["reviewed_sha"] == PRODUCT_SHA
    assert template["reviewed_sha"] == PRODUCT_SHA
    assert template["reviewed_artifact_path"] == package_path
    assert template["reviewed_artifact_sha256"] == _sha256(package_path)


def test_step18_template_is_bound_to_exact_current_review_package() -> None:
    package_path = "docs/quality/review_packages/step_18_review_package.json"
    template = _load("docs/quality/reviews/step_18_independent_review.template.json")
    package = _load(package_path)

    assert package["reviewed_sha"] == PRODUCT_SHA
    assert template["reviewed_sha"] == PRODUCT_SHA
    assert template["reviewed_artifact_path"] == package_path
    assert template["reviewed_artifact_sha256"] == _sha256(package_path)


def test_handoff_names_exact_current_package_hashes() -> None:
    handoff = (ROOT / "docs/quality/INDEPENDENT_REVIEW_HANDOFF.md").read_text(encoding="utf-8")
    for package_path in (
        "docs/quality/review_packages/step_16_review_package.json",
        "docs/quality/review_packages/step_18_review_package.json",
    ):
        assert _sha256(package_path) in handoff
    assert PRODUCT_SHA in handoff
