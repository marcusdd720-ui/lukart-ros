from __future__ import annotations

from types import MappingProxyType

import pytest

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineSafety,
    FilingTopologyStatus,
    MeritsStrength,
    RemedyAdmissibility,
    RemedyOption,
    StrategyDecisionStatus,
    StrategyOption,
    VerificationLevel,
)
from core.cirp.strategy import (
    ConsolidationAssessment,
    ConsolidationAssessmentStatus,
    FilingTopologyGuard,
    StrategyGuard,
)


def remedy(
    remedy_id: str,
    *,
    status: RemedyAdmissibility = RemedyAdmissibility.VERIFIED_AVAILABLE,
    target_authority: str = "synthetic-target",
    filing_authority: str = "synthetic-filing-authority",
    filing_via: str | None = "synthetic-route",
) -> RemedyOption:
    blockers = () if status is RemedyAdmissibility.VERIFIED_AVAILABLE else ("synthetic blocker",)
    return RemedyOption(
        remedy_id=remedy_id,
        remedy_type="SYNTHETIC_REVIEW",
        target_authority=target_authority,
        filing_authority=filing_authority,
        filing_via=filing_via,
        applicable_rule_ids=(f"rule:{remedy_id}@1#" + "a" * 64,),
        deadline_id=f"deadline:{remedy_id}",
        formal_requirements=("synthetic-signature",),
        required_evidence=(f"requirement:{remedy_id}",),
        preserves_options=("synthetic-option",),
        waives_options=(),
        admissibility_status=status,
        blockers=blockers,
    )


def strategy(
    strategy_id: str,
    *,
    remedy_ids: tuple[str, ...] = ("remedy:a",),
    required_evidence: tuple[str, ...] = ("evidence:decisive",),
    deadline_safety: DeadlineSafety = DeadlineSafety.SAFE,
    admissibility: VerificationLevel = VerificationLevel.VERIFIED,
    unresolved: tuple[str, ...] = (),
    risks: tuple[str, ...] = (),
) -> StrategyOption:
    return StrategyOption(
        strategy_id=strategy_id,
        objective="Synthetic objective",
        remedy_ids=remedy_ids,
        proposed_actions=("synthetic-action",),
        required_evidence=required_evidence,
        deadline_safety=deadline_safety,
        admissibility=admissibility,
        merits_strength=MeritsStrength.MODERATE,
        preserves_options=("synthetic-option",),
        closes_options=(),
        risks=risks,
        advantages=("synthetic-advantage",),
        disadvantages=(),
        unresolved=unresolved,
    )


def decide(
    *options: StrategyOption,
    remedies: tuple[RemedyOption, ...] = (remedy("remedy:a"),),
    evidence: tuple[str, ...] = ("evidence:decisive",),
    decisive_evidence: tuple[str, ...] = ("evidence:decisive",),
    decisive_rules: tuple[str, ...] = ("rule:synthetic:strategy@1",),
):
    return StrategyGuard().decide(
        options=tuple(options),
        remedies=remedies,
        available_evidence_ids=evidence,
        decisive_evidence=decisive_evidence,
        decisive_rules=decisive_rules,
    )


def consolidation(
    groups: tuple[tuple[str, ...], ...],
    *,
    status: ConsolidationAssessmentStatus = ConsolidationAssessmentStatus.VERIFIED,
    blockers: tuple[str, ...] = (),
) -> ConsolidationAssessment:
    verified = status is ConsolidationAssessmentStatus.VERIFIED
    return ConsolidationAssessment(
        assessment_id="consolidation:synthetic:1",
        remedy_groups=groups,
        status=status,
        evidence_refs=("evidence:consolidation",) if verified else (),
        rule_refs=("rule:synthetic:consolidation@1",) if verified else (),
        rationale="Synthetic consolidation assessment",
        blockers=blockers,
    )


def test_exactly_one_verified_safe_strategy_can_be_recommended() -> None:
    decision = decide(strategy("strategy:a"))

    assert decision.decision_status is StrategyDecisionStatus.RECOMMENDED
    assert decision.selected_strategy_id == "strategy:a"
    assert decision.decisive_evidence == ("evidence:decisive",)
    assert decision.decisive_rules == ("rule:synthetic:strategy@1",)


def test_multiple_safe_strategies_require_decision_without_fake_ranking() -> None:
    decision = decide(strategy("strategy:a"), strategy("strategy:b"))

    assert decision.decision_status is StrategyDecisionStatus.DECISION_REQUIRED
    assert decision.selected_strategy_id is None
    assert decision.decisive_evidence == ()


def test_missing_strategy_evidence_fails_closed() -> None:
    decision = decide(
        strategy("strategy:a", required_evidence=("evidence:missing",)),
        evidence=("evidence:decisive",),
    )

    assert decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert "Missing required strategy evidence" in decision.rejection_reasons["strategy:a"]


def test_provisional_remedy_prevents_recommendation() -> None:
    decision = decide(
        strategy("strategy:a"),
        remedies=(remedy("remedy:a", status=RemedyAdmissibility.PROVISIONALLY_AVAILABLE),),
    )

    assert decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert "not fully verified" in decision.rejection_reasons["strategy:a"]


def test_explicit_deadline_risk_returns_no_safe_option() -> None:
    decision = decide(strategy("strategy:a", deadline_safety=DeadlineSafety.RISK))

    assert decision.decision_status is StrategyDecisionStatus.NO_SAFE_OPTION
    assert "deadline risk" in decision.rejection_reasons["strategy:a"]


def test_unknown_deadline_or_admissibility_is_evidence_limited() -> None:
    unknown_deadline = decide(
        strategy("strategy:a", deadline_safety=DeadlineSafety.UNKNOWN)
    )
    unknown_admissibility = decide(
        strategy("strategy:b", admissibility=VerificationLevel.UNKNOWN)
    )

    assert unknown_deadline.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert unknown_admissibility.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE


def test_unresolved_strategy_dependency_prevents_recommendation() -> None:
    decision = decide(strategy("strategy:a", unresolved=("resolve synthetic dependency",)))

    assert decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert decision.selected_strategy_id is None


def test_safe_candidate_without_decisive_basis_abstains() -> None:
    decision = decide(
        strategy("strategy:a"),
        decisive_evidence=(),
        decisive_rules=(),
    )

    assert decision.decision_status is StrategyDecisionStatus.ABSTAIN
    assert decision.selected_strategy_id is None
    assert "decisive evidence" in decision.rationale


def test_no_strategy_options_abstains() -> None:
    decision = decide()

    assert decision.decision_status is StrategyDecisionStatus.ABSTAIN
    assert decision.selected_strategy_id is None


def test_decisive_evidence_must_exist_in_available_evidence() -> None:
    with pytest.raises(CIRPContractError, match="not present"):
        decide(
            strategy("strategy:a"),
            decisive_evidence=("evidence:not-present",),
        )


def test_duplicate_strategy_or_remedy_identity_is_rejected() -> None:
    with pytest.raises(CIRPContractError, match="duplicate strategy_id"):
        decide(strategy("strategy:a"), strategy("strategy:a"))

    with pytest.raises(CIRPContractError, match="duplicate remedy_id"):
        decide(
            strategy("strategy:a"),
            remedies=(remedy("remedy:a"), remedy("remedy:a")),
        )


def test_rejected_strategy_has_explicit_rejection_reason() -> None:
    decision = decide(
        strategy("strategy:safe"),
        strategy("strategy:risky", deadline_safety=DeadlineSafety.RISK),
    )

    assert decision.decision_status is StrategyDecisionStatus.RECOMMENDED
    assert decision.selected_strategy_id == "strategy:safe"
    assert decision.rejected_strategy_ids == ("strategy:risky",)
    assert decision.rejection_reasons == MappingProxyType(
        {"strategy:risky": "Strategy carries explicit deadline risk."}
    )


def test_single_verified_remedy_is_single_filing_safe() -> None:
    topology = FilingTopologyGuard().decide(
        strategy=strategy("strategy:a"),
        remedies=(remedy("remedy:a"),),
    )

    assert topology.status is FilingTopologyStatus.SINGLE_FILING_SAFE
    assert topology.filing_count == 1
    assert topology.combined_remedies == ("remedy:a",)


def test_multiple_remedies_require_explicit_consolidation_assessment() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b"),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected,
        remedies=(remedy("remedy:a"), remedy("remedy:b")),
    )

    assert topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN
    assert topology.filing_count == 0
    assert topology.blockers


def test_verified_exact_single_group_allows_one_filing() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b"),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected,
        remedies=(remedy("remedy:a"), remedy("remedy:b")),
        consolidation=consolidation((("remedy:a", "remedy:b"),)),
    )

    assert topology.status is FilingTopologyStatus.SINGLE_FILING_SAFE
    assert topology.filing_count == 1
    assert topology.combined_remedies == ("remedy:a", "remedy:b")


def test_verified_partition_can_require_multiple_filings() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b", "remedy:c"),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected,
        remedies=(
            remedy("remedy:a"),
            remedy("remedy:b"),
            remedy("remedy:c", target_authority="synthetic-other-target"),
        ),
        consolidation=consolidation(
            (("remedy:a", "remedy:b"), ("remedy:c",))
        ),
    )

    assert topology.status is FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED
    assert topology.filing_count == 2
    assert topology.combined_remedies == ("remedy:a", "remedy:b")
    assert topology.separated_remedies == ("remedy:c",)


def test_consolidation_group_cannot_mix_incompatible_routes() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b"),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected,
        remedies=(
            remedy("remedy:a"),
            remedy("remedy:b", filing_via="different-route"),
        ),
        consolidation=consolidation((("remedy:a", "remedy:b"),)),
    )

    assert topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN
    assert "incompatible filing routes" in topology.blockers[0]


def test_consolidation_assessment_must_cover_exact_remedy_set() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b"),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected,
        remedies=(remedy("remedy:a"), remedy("remedy:b")),
        consolidation=consolidation((("remedy:a",),)),
    )

    assert topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN
    assert "exact selected remedy set" in topology.rationale


def test_unknown_or_conflicting_consolidation_fails_closed() -> None:
    selected = strategy(
        "strategy:a",
        remedy_ids=("remedy:a", "remedy:b"),
    )
    for status in (
        ConsolidationAssessmentStatus.UNKNOWN,
        ConsolidationAssessmentStatus.CONFLICTING,
    ):
        topology = FilingTopologyGuard().decide(
            strategy=selected,
            remedies=(remedy("remedy:a"), remedy("remedy:b")),
            consolidation=consolidation(
                (("remedy:a", "remedy:b"),),
                status=status,
                blockers=("resolve synthetic consolidation evidence",),
            ),
        )
        assert topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN
        assert topology.blockers


def test_unverified_remedy_blocks_topology_certification() -> None:
    topology = FilingTopologyGuard().decide(
        strategy=strategy("strategy:a"),
        remedies=(remedy("remedy:a", status=RemedyAdmissibility.UNKNOWN),),
    )

    assert topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN
    assert topology.blockers


def test_strategy_without_remedy_has_no_filing_required() -> None:
    topology = FilingTopologyGuard().decide(
        strategy=strategy("strategy:a", remedy_ids=()),
        remedies=(),
    )

    assert topology.status is FilingTopologyStatus.NO_FILING_REQUIRED
    assert topology.filing_count == 0


def test_consolidation_contract_rejects_duplicate_membership_and_weak_verification() -> None:
    with pytest.raises(CIRPContractError, match="multiple consolidation groups"):
        consolidation((("remedy:a", "remedy:b"), ("remedy:a",)))

    with pytest.raises(CIRPContractError, match="requires evidence_refs and rule_refs"):
        ConsolidationAssessment(
            assessment_id="consolidation:synthetic:weak",
            remedy_groups=(("remedy:a", "remedy:b"),),
            status=ConsolidationAssessmentStatus.VERIFIED,
            evidence_refs=(),
            rule_refs=(),
            rationale="Synthetic weak assessment",
        )
