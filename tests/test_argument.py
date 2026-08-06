"""Tests for Argument contract (case.py 1.5.0)"""

from __future__ import annotations

import pytest

from knowledge.models.case import (
    Argument,
    ArgumentStatus,
    Case,
    Fact,
    LegalBasis,
    LegalIssue,
)


def test_argument_requires_issue_id() -> None:
    arg = Argument(issue_id="", claim="Teza")
    with pytest.raises(ValueError, match="issue_id cannot be empty"):
        arg.validate()


def test_argument_requires_claim() -> None:
    arg = Argument(issue_id="some-id", claim="")
    with pytest.raises(ValueError, match="claim cannot be empty"):
        arg.validate()


def test_add_argument_rejects_unknown_issue() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Fakt")
    case.add_fact(fact)
    issue = LegalIssue(question="Pytanie?", fact_ids=[fact.id])
    case.add_issue(issue)

    arg = Argument(issue_id="non-existent", claim="Teza")
    with pytest.raises(ValueError, match="unknown issue"):
        case.add_argument(arg)


def test_add_argument_rejects_unknown_facts() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Fakt")
    case.add_fact(fact)
    issue = LegalIssue(question="Pytanie?", fact_ids=[fact.id])
    case.add_issue(issue)

    arg = Argument(
        issue_id=issue.id,
        claim="Teza",
        support_fact_ids=["ghost-fact"],
    )
    with pytest.raises(ValueError, match="unknown facts"):
        case.add_argument(arg)


def test_add_argument_success() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Darowizna dokonana")
    case.add_fact(fact)
    basis = LegalBasis(reference="art. 7 k.p.k.")
    case.add_legal_basis(basis)
    issue = LegalIssue(
        question="Czy darowizna skuteczna?",
        fact_ids=[fact.id],
        legal_basis_ids=[basis.id],
    )
    case.add_issue(issue)

    arg = Argument(
        issue_id=issue.id,
        claim="Czynności oparte były na dokumentach",
        support_fact_ids=[fact.id],
        legal_basis_ids=[basis.id],
        status=ArgumentStatus.ADVANCED,
    )
    case.add_argument(arg)

    assert len(case.arguments) == 1
    assert case.get_argument(arg.id) is not None
    assert case.arguments[0].status == ArgumentStatus.ADVANCED