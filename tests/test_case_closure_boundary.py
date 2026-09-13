from __future__ import annotations

import pytest

from knowledge.models.case import Case, CaseStatus


def test_generic_advance_to_refuses_closed_without_governed_closure() -> None:
    case = Case(id="CASE-SYNTHETIC-CLOSURE")

    with pytest.raises(ValueError, match="explicit governed closure"):
        case.advance_to(CaseStatus.CLOSED)

    assert case.status is CaseStatus.NEW


def test_generic_advance_to_still_allows_nonclosure_transition() -> None:
    case = Case(id="CASE-SYNTHETIC-CLOSURE")

    case.advance_to(CaseStatus.ANALYSIS)

    assert case.status is CaseStatus.ANALYSIS
