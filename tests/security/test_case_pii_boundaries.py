from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "case_testy"
PESEL_LIKE = re.compile(r"(?<!\d)\d{11}(?!\d)")
EMAIL_LIKE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def test_case_testy_fixtures_are_explicitly_synthetic() -> None:
    fixtures = sorted(FIXTURE_ROOT.glob("*.json"))
    assert fixtures, "CASE-TESTY synthetic fixture set must not be empty"
    for path in fixtures:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("synthetic") is True, f"fixture must be explicitly synthetic: {path}"
        assert str(payload.get("case_id", "")).startswith("synthetic-"), path


def test_case_testy_fixtures_do_not_contain_obvious_personal_identifiers() -> None:
    for path in sorted(FIXTURE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert PESEL_LIKE.search(text) is None, (
            f"PESEL-like identifier in synthetic fixture: {path}"
        )
        assert EMAIL_LIKE.search(text) is None, (
            f"email-like identifier in synthetic fixture: {path}"
        )
