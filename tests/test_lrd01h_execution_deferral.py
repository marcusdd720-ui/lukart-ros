from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LRD_01H = ROOT / "docs" / "PROVIDER_DURABLE_STORAGE_WORM_V1.md"


def test_lrd01h_live_aws_execution_is_deferred_without_promoting_provider_evidence() -> None:
    text = LRD_01H.read_text(encoding="utf-8")

    assert "Status: `IMPLEMENTATION CANDIDATE / REAL PROVIDER EVIDENCE REQUIRED`" in text
    assert "deferred until **March 2027**" in text
    assert "new explicit owner/business decision supersedes this deferral" in text
    assert "External provider evidence remains `INCOMPLETE`" in text
    assert "no AWS account" in text
    assert "no\nmock, fixture, repository CI result or planning text may be promoted" in text


def test_lrd01h_deferral_keeps_provider_neutral_continuation_order_explicit() -> None:
    text = LRD_01H.read_text(encoding="utf-8")

    required_order = (
        "1. post-01H gap audit;",
        "2. offline long-range survivability;",
        "3. crypto migration/renewal;",
        "4. cross-environment replay;",
        "5. expanded critical-invariant verification;",
        "6. further provider-neutral durability/recovery;",
        "7. live AWS LRD-01H closure work in the March 2027 execution window.",
    )
    positions = [text.index(item) for item in required_order]

    assert positions == sorted(positions)
    assert "Subsequent work must not inherit, imply or claim an\nLRD-01H provider PASS." in text
