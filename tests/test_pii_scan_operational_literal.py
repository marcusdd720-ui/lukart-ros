from scripts.pii_scan import (
    GOVERNANCE_MARKDOWN_RUN_PATHS,
    OPERATIONAL_READINESS_IDENTIFIER_LITERAL,
    OPERATIONAL_READINESS_IDENTIFIER_LITERAL_PATH,
    PATTERNS,
    _pii_scan_text,
)


def test_operational_identifier_literal_is_masked_only_at_canonical_path() -> None:
    source = f"allowed = {OPERATIONAL_READINESS_IDENTIFIER_LITERAL}\n"
    masked = _pii_scan_text(
        source,
        relative=OPERATIONAL_READINESS_IDENTIFIER_LITERAL_PATH,
    )
    assert not PATTERNS["NIP-like number"].search(masked)

    unmasked = _pii_scan_text(source, relative="tests/example.py")
    assert PATTERNS["NIP-like number"].search(unmasked)


def test_operational_path_still_detects_unrelated_nip_like_token() -> None:
    unrelated = "12345" + "67890"
    source = (
        f"allowed = {OPERATIONAL_READINESS_IDENTIFIER_LITERAL}\n"
        f"external_value = '{unrelated}'\n"
    )
    masked = _pii_scan_text(
        source,
        relative=OPERATIONAL_READINESS_IDENTIFIER_LITERAL_PATH,
    )
    assert PATTERNS["NIP-like number"].search(masked)


def test_duplicate_identifier_literal_fails_closed() -> None:
    source = (
        f"a = {OPERATIONAL_READINESS_IDENTIFIER_LITERAL}\n"
        f"b = {OPERATIONAL_READINESS_IDENTIFIER_LITERAL}\n"
    )
    masked = _pii_scan_text(
        source,
        relative=OPERATIONAL_READINESS_IDENTIFIER_LITERAL_PATH,
    )
    assert PATTERNS["NIP-like number"].search(masked)


def test_canonical_governance_run_reference_masks_pesel_shaped_run_id() -> None:
    source = "Governance Closure PR Preparation run `34254376877` generated PR #185.\n"
    for path in GOVERNANCE_MARKDOWN_RUN_PATHS:
        masked = _pii_scan_text(source, relative=path)
        assert not PATTERNS["PESEL-like 11 digits"].search(masked)


def test_canonical_governance_path_still_detects_untyped_pesel_shaped_value() -> None:
    source = (
        "Governance Closure PR Preparation run `34254376877` generated PR #185.\n"
        "unrelated_value = `12345678901`\n"
    )
    masked = _pii_scan_text(source, relative="docs/POST_HARDCORE_ROADMAP.md")
    assert PATTERNS["PESEL-like 11 digits"].search(masked)


def test_governance_run_reference_is_not_masked_outside_canonical_paths() -> None:
    source = "Governance Closure PR Preparation run `34254376877` generated PR #185.\n"
    masked = _pii_scan_text(source, relative="docs/example.md")
    assert PATTERNS["PESEL-like 11 digits"].search(masked)
