from __future__ import annotations

import json

from scripts.pii_scan import CRYPTO_DIGEST, PATTERNS, _pii_scan_text

EVIDENCE_PATH = (
    "evidence/governance_closure/gov-auto-01/"
    "132312e157f5d6ccc13aa40d48e34e5c3732c908.json"
)


def _labels(text: str, *, relative: str = "") -> set[str]:
    scan_text = _pii_scan_text(text, relative=relative)
    return {label for label, pattern in PATTERNS.items() if pattern.search(scan_text)}


def _canonical_evidence(run_id: int) -> dict[str, object]:
    return {
        "schema": "lukart.closure-preparation-evidence.v1",
        "authority": "closure-preparation-only",
        "result": "PREPARED_NOT_CLOSED",
        "stage_id": "GOV-AUTO-01",
        "pr_workflows": [{"run_id": run_id}],
        "post_merge_workflows": [{"run_id": run_id + 1}],
    }


def test_sha1_and_sha256_are_masked_before_pii_matching() -> None:
    sha1 = "32da9ed623c193ff234da5c0afa273b944e52390"
    sha256 = "9bf3851073508a007b42ce0ebc6911e7ab7107eca7e7355d8d2cf667e0a388a9"

    assert CRYPTO_DIGEST.fullmatch(sha1)
    assert CRYPTO_DIGEST.fullmatch(sha256)
    assert _labels(f"revision={sha1} digest={sha256}") == set()


def test_real_pii_patterns_remain_detectable_next_to_hashes() -> None:
    sha256 = "1aab28f24251c8dadb98c5329cf218211927c825f875aed7b286436c8beafb94"
    phone = " ".join(("500", "600", "700"))
    email = "@".join(("reviewer", ".".join(("example", "org"))))
    text = f"digest={sha256} contact={phone} email={email}"

    labels = _labels(text)

    assert "phone-like number" in labels
    assert "email" in labels


def test_nip_and_pesel_like_values_are_not_masked() -> None:
    nip = "-".join(("123", "456", "32", "18"))
    pesel = "".join(("44051", "401458"))
    labels = _labels(f"nip={nip} pesel={pesel}")

    assert "NIP-like number" in labels
    assert "PESEL-like 11 digits" in labels


def test_non_digest_hex_sequence_is_not_blanket_ignored() -> None:
    value = "abc" + "500" + "600" + "700" + "def"

    assert not CRYPTO_DIGEST.fullmatch(value)
    # The scanner does not promise to detect digits embedded in arbitrary text;
    # this regression only proves that non-digest strings are not masked wholesale.
    assert _pii_scan_text(value) == value


def test_canonical_github_run_id_is_not_treated_as_pesel() -> None:
    run_id = int("34237" + "264037")
    labels = _labels(json.dumps(_canonical_evidence(run_id)), relative=EVIDENCE_PATH)

    assert "PESEL-like 11 digits" not in labels


def test_unrelated_eleven_digit_value_in_same_evidence_still_fails() -> None:
    run_id = int("34237" + "264037")
    personal_shape = "12345" + "678901"
    payload = _canonical_evidence(run_id)
    payload["unrelated_number"] = personal_shape

    labels = _labels(json.dumps(payload), relative=EVIDENCE_PATH)

    assert "PESEL-like 11 digits" in labels


def test_noncanonical_evidence_does_not_receive_run_id_exception() -> None:
    run_id = int("34237" + "264037")
    payload = _canonical_evidence(run_id)
    payload["authority"] = "unexpected-authority"

    labels = _labels(json.dumps(payload), relative=EVIDENCE_PATH)

    assert "PESEL-like 11 digits" in labels
