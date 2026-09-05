from __future__ import annotations

from scripts.pii_scan import CRYPTO_DIGEST, PATTERNS, _pii_scan_text


def _labels(text: str) -> set[str]:
    scan_text = _pii_scan_text(text)
    return {label for label, pattern in PATTERNS.items() if pattern.search(scan_text)}


def test_sha1_and_sha256_are_masked_before_pii_matching() -> None:
    sha1 = "32da9ed623c193ff234da5c0afa273b944e52390"
    sha256 = "9bf3851073508a007b42ce0ebc6911e7ab7107eca7e7355d8d2cf667e0a388a9"

    assert CRYPTO_DIGEST.fullmatch(sha1)
    assert CRYPTO_DIGEST.fullmatch(sha256)
    assert _labels(f"revision={sha1} digest={sha256}") == set()


def test_real_pii_patterns_remain_detectable_next_to_hashes() -> None:
    sha256 = "1aab28f24251c8dadb98c5329cf218211927c825f875aed7b286436c8beafb94"
    text = f"digest={sha256} contact=500 600 700 email=reviewer@example.org"

    labels = _labels(text)

    assert "phone-like number" in labels
    assert "email" in labels


def test_nip_and_pesel_like_values_are_not_masked() -> None:
    labels = _labels("nip=123-456-32-18 pesel=44051401458")

    assert "NIP-like number" in labels
    assert "PESEL-like 11 digits" in labels


def test_non_digest_hex_sequence_is_not_blanket_ignored() -> None:
    value = "abc500600700def"

    assert not CRYPTO_DIGEST.fullmatch(value)
    # The scanner does not promise to detect digits embedded in arbitrary text;
    # this regression only proves that non-digest strings are not masked wholesale.
    assert _pii_scan_text(value) == value
