from __future__ import annotations

import pytest

from knowledge.models.case import Case, CaseStatus


def test_generic_advance_to_refuses_filed_without_governed_filing() -> None:
    case = Case(id="CASE-SYNTHETIC-FILING")

    with pytest.raises(ValueError, match="explicit governed filing"):
        case.advance_to(CaseStatus.FILED)

    assert case.status is CaseStatus.NEW
