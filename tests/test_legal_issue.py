"""
Tests for closed LegalIssue contract (case.py 1.4.0)
"""

from __future__ import annotations

import pytest

from knowledge.models.case import (
    Case,
    CaseStatus,
    Fact,
    LegalBasis,
    LegalIssue,
)


def test_legal_issue_requires_question() -> None:
    issue = LegalIssue(question="", fact_ids=["f1"])
    with pytest.raises(ValueError, match="question cannot be empty"):
        issue.validate()


def test_legal_issue_requires_at_least_one_fact_id() -> None:
    issue = LegalIssue(question="Czy czynność była skuteczna?", fact_ids=[])
    with pytest.raises(ValueError, match="fact_ids must contain at least one"):
        issue.validate()


def test_add_issue_rejects_unknown_fact_ids() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Darowizna została dokonana")
    case.add_fact(fact)

    issue = LegalIssue(
        question="Czy darowizna jest skuteczna?",
        fact_ids=["non-existent-id"],
    )
    with pytest.raises(ValueError, match="unknown facts"):
        case.add_issue(issue)


def test_add_issue_rejects_unknown_legal_basis_ids() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Darowizna została dokonana")
    case.add_fact(fact)

    issue = LegalIssue(
        question="Czy darowizna jest skuteczna?",
        fact_ids=[fact.id],
        legal_basis_ids=["non-existent-basis"],
    )
    with pytest.raises(ValueError, match="unknown legal bases"):
        case.add_issue(issue)


def test_add_issue_success_and_status_transition() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Darowizna została dokonana 14.05.2025")
    case.add_fact(fact)

    basis = LegalBasis(reference="art. 888 k.c.")
    case.add_legal_basis(basis)

    issue = LegalIssue(
        question="Czy darowizna pojazdu była skuteczna?",
        fact_ids=[fact.id],
        legal_basis_ids=[basis.id],
        hypothesis="Darowizna spełnia przesłanki art. 888 k.c.",
    )
    case.add_issue(issue)

    assert len(case.legal_issues) == 1
    assert case.legal_issues[0].id == issue.id
    assert case.status == CaseStatus.ANALYSIS
    assert case.get_issue(issue.id) is not None


def test_add_issue_without_legal_basis_ids_is_allowed() -> None:
    case = Case(title="Test")
    fact = Fact(statement="Pojazd został zarejestrowany")
    case.add_fact(fact)

    issue = LegalIssue(
        question="Czy rejestracja ma skutek wobec osób trzecich?",
        fact_ids=[fact.id],
    )
    case.add_issue(issue)

    assert len(case.legal_issues) == 1
    assert case.legal_issues[0].legal_basis_ids == []