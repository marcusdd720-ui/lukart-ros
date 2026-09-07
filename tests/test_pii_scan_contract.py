from __future__ import annotations

from scripts.pii_scan import PATTERNS, _is_pii_text_candidate, _pii_scan_text


def test_generated_pep751_lock_is_not_naively_pii_scanned() -> None:
    assert _is_pii_text_candidate("pylock.toml", ".toml") is False


def test_ordinary_toml_remains_in_fail_closed_pii_scope() -> None:
    assert _is_pii_text_candidate("config/example.toml", ".toml") is True
    synthetic_pesel = "440" + "514" + "01458"
    text = _pii_scan_text(f'owner = "{synthetic_pesel}"\n')
    assert PATTERNS["PESEL-like 11 digits"].search(text)


def test_dependency_lock_exemption_is_path_specific() -> None:
    assert _is_pii_text_candidate("config/pylock.toml", ".toml") is True
    assert _is_pii_text_candidate("reports/pylock.toml", ".toml") is True
