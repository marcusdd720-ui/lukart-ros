from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT / "docs" / "WORKING_PRINCIPLES.md"
AGENTS = ROOT / "AGENTS.md"
FOUNDATION = ROOT / "FOUNDATION.md"
MASTER_PLAN = ROOT / "MASTER_PLAN.md"


def test_canonical_working_principles_fit_instruction_limit_and_keep_core_contract() -> None:
    text = WORKING.read_text(encoding="utf-8")

    assert 6_500 <= len(text) <= 8_000
    for required in (
        "CLOSED / ENGINEERING PASS",
        "HARD BLOCKER",
        "fresh SHA",
        "queued/pending/in_progress",
        "poll → inspect → poll",
        "Canonical Case Ledger",
        "INDEPENDENT_REVIEW_REQUIRED",
        "Best-Justified Solution != Most Complex Solution",
        "Memory = trwałe zasady",
        "GitHub = live SHA/PR/CI/roadmap/release",
    ):
        assert required in text


def test_agents_is_thin_bridge_not_second_full_standard() -> None:
    text = AGENTS.read_text(encoding="utf-8")

    assert len(text) < 6_000
    assert "docs/WORKING_PRINCIPLES.md" in text
    assert "single canonical living execution/trust standard" in text
    assert "MUST NOT duplicate the full operating standard" in text
    assert text.count("\n## ") <= 8


def test_foundation_and_master_plan_point_to_the_same_canonical_standard() -> None:
    foundation = FOUNDATION.read_text(encoding="utf-8")
    master_plan = MASTER_PLAN.read_text(encoding="utf-8")

    assert "docs/WORKING_PRINCIPLES.md" in foundation
    assert "single canonical living execution/trust standard" in foundation
    assert "docs/WORKING_PRINCIPLES.md" in master_plan
    assert "canonical living engineering standard" in master_plan


def test_no_second_markdown_file_claims_the_canonical_standard_heading() -> None:
    canonical_heading = "# LUKART ROS — KANONICZNY STANDARD INŻYNIERSKI"
    owners = [
        path
        for path in ROOT.rglob("*.md")
        if canonical_heading in path.read_text(encoding="utf-8", errors="replace")
    ]

    assert owners == [WORKING]
