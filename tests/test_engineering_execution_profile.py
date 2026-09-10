from pathlib import Path

CANON = Path("docs/WORKING_PRINCIPLES.md")
PROFILE = Path("docs/ENGINEERING_EXECUTION_PROFILE.md")


def test_canonical_standard_keeps_governance_invariants() -> None:
    text = CANON.read_text(encoding="utf-8")

    assert len(text) <= 8000
    assert "docs/WORKING_PRINCIPLES.md` = jedyny pełny living standard" in text
    assert "Exact-SHA PASS wymaga terminalnego dozwolonego `SUCCESS`" in text
    assert "realnego DR drill" in text
    assert "ordered follow-up bez scope creep" in text


def test_execution_profile_is_thin_and_non_authoritative() -> None:
    text = PROFILE.read_text(encoding="utf-8")

    assert len(text) <= 2500
    assert "NON-AUTHORITATIVE OPERATIONAL SHORTHAND" in text
    assert "Ten plik nie jest drugim standardem" in text
    assert "docs/WORKING_PRINCIPLES.md" in text
    assert "Przy konflikcie wygrywa aktualny GitHub canon" in text


def test_execution_profile_preserves_claim_and_scope_boundaries() -> None:
    text = PROFILE.read_text(encoding="utf-8")

    assert "Nie fabrykuj human/independent/security/external review" in text
    assert "CI/symulacja nie dowodzi fizycznej separacji" in text
    assert "nowe trust boundaries" in text
    assert "trafiają do ordered follow-up" in text
