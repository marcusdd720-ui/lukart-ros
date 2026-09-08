from scripts.pii_scan import (
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
