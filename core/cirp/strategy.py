"""Fail-closed strategy and filing-topology semantics for CIRP-04.

CIRP-04 deliberately avoids synthetic numeric scoring. Strategy recommendation is
bounded to a single fully verified/safe candidate and requires explicit decisive
evidence and rule references. When several safe candidates remain, the runtime
returns DECISION_REQUIRED instead of manufacturing a ranking.

Filing consolidation is also evidence-bound. More than one remedy may share a
filing only when an explicit, verified consolidation assessment provides an exact
partition of the selected remedies and its evidence/rule basis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineSafety,
    FilingTopologyDecision,
    FilingTopologyStatus,
    RemedyAdmissibility,
    RemedyOption,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyOption,
    VerificationLevel,
)


class ConsolidationAssessmentStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CIRPContractError(f"{field_name} cannot contain control characters")
    return value


def _unique_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_nonblank(item, field_name=field_name) for item in values)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ConsolidationAssessment:
    """Evidence-bound proposed filing partition for an exact remedy set."""

    assessment_id: str
    remedy_groups: tuple[tuple[str, ...], ...]
    status: ConsolidationAssessmentStatus
    evidence_refs: tuple[str, ...]
    rule_refs: tuple[str, ...]
    rationale: str
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_id",
            _require_nonblank(self.assessment_id, field_name="assessment_id"),
        )
        object.__setattr__(
            self,
            "rationale",
            _require_nonblank(self.rationale, field_name="rationale"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _unique_nonblank(self.evidence_refs, field_name="evidence_refs"),
        )
        object.__setattr__(
            self,
            "rule_refs",
            _unique_nonblank(self.rule_refs, field_name="rule_refs"),
        )
        object.__setattr__(
            self,
            "blockers",
            _unique_nonblank(self.blockers, field_name="blockers"),
        )

        normalized_groups: list[tuple[str, ...]] = []
        seen: set[str] = set()
        for index, group in enumerate(self.remedy_groups):
            normalized = _unique_nonblank(group, field_name=f"remedy_groups[{index}]")
            if not normalized:
                raise CIRPContractError("consolidation remedy groups cannot be empty")
            overlap = seen.intersection(normalized)
            if overlap:
                raise CIRPContractError(
                    "a remedy cannot occur in multiple consolidation groups: "
                    + ", ".join(sorted(overlap))
                )
            seen.update(normalized)
            normalized_groups.append(normalized)
        if not normalized_groups:
            raise CIRPContractError("consolidation assessment requires remedy_groups")
        object.__setattr__(self, "remedy_groups", tuple(normalized_groups))

        if self.status is ConsolidationAssessmentStatus.VERIFIED:
            if self.blockers:
                raise CIRPContractError("VERIFIED consolidation assessment cannot have blockers")
            if not self.evidence_refs or not self.rule_refs:
                raise CIRPContractError(
                    "VERIFIED consolidation assessment requires evidence_refs and rule_refs"
                )
        elif not self.blockers:
            raise CIRPContractError(
                f"{self.status.value} consolidation assessment requires blockers"
            )

    @property
    def remedy_ids(self) -> tuple[str, ...]:
        return tuple(item for group in self.remedy_groups for item in group)


class StrategyGuard:
    """Recommend only when one strategy remains fully verified and safe."""

    def decide(
        self,
        *,
        options: tuple[StrategyOption, ...],
        remedies: tuple[RemedyOption, ...],
        available_evidence_ids: tuple[str, ...],
        decisive_evidence: tuple[str, ...] = (),
        decisive_rules: tuple[str, ...] = (),
    ) -> StrategyDecision:
        if not options:
            return StrategyDecision(
                selected_strategy_id=None,
                decision_status=StrategyDecisionStatus.ABSTAIN,
                rationale="No strategy options were supplied for evaluation.",
                rejected_strategy_ids=(),
                rejection_reasons={},
                decisive_evidence=(),
                decisive_rules=(),
                unresolved_risks=("Generate evidence-bound strategy options.",),
            )

        option_map: dict[str, StrategyOption] = {}
        for option in options:
            if option.strategy_id in option_map:
                raise CIRPContractError(f"duplicate strategy_id: {option.strategy_id}")
            option_map[option.strategy_id] = option

        remedy_map: dict[str, RemedyOption] = {}
        for remedy in remedies:
            if remedy.remedy_id in remedy_map:
                raise CIRPContractError(f"duplicate remedy_id: {remedy.remedy_id}")
            remedy_map[remedy.remedy_id] = remedy

        available_evidence = set(
            _unique_nonblank(available_evidence_ids, field_name="available_evidence_ids")
        )
        decisive_evidence = _unique_nonblank(
            decisive_evidence, field_name="decisive_evidence"
        )
        decisive_rules = _unique_nonblank(decisive_rules, field_name="decisive_rules")
        if set(decisive_evidence) - available_evidence:
            missing = sorted(set(decisive_evidence) - available_evidence)
            raise CIRPContractError(
                "decisive evidence is not present in available evidence: " + ", ".join(missing)
            )

        eligible: list[StrategyOption] = []
        rejection_reasons: dict[str, str] = {}
        uncertainty_seen = False

        for option in options:
            reason, uncertain = self._ineligibility_reason(
                option=option,
                remedy_map=remedy_map,
                available_evidence=available_evidence,
            )
            if reason is None:
                eligible.append(option)
            else:
                rejection_reasons[option.strategy_id] = reason
                uncertainty_seen = uncertainty_seen or uncertain

        rejected_ids = tuple(rejection_reasons)
        unresolved_risks = tuple(
            dict.fromkeys(
                risk
                for option in eligible
                for risk in (*option.risks, *option.unresolved)
            )
        )

        if len(eligible) > 1:
            return StrategyDecision(
                selected_strategy_id=None,
                decision_status=StrategyDecisionStatus.DECISION_REQUIRED,
                rationale=(
                    "Multiple fully verified and deadline-safe strategies remain; "
                    "CIRP does not manufacture a numeric ranking."
                ),
                rejected_strategy_ids=rejected_ids,
                rejection_reasons=rejection_reasons,
                decisive_evidence=(),
                decisive_rules=(),
                unresolved_risks=unresolved_risks,
            )

        if len(eligible) == 1:
            selected = eligible[0]
            if not decisive_evidence or not decisive_rules:
                return StrategyDecision(
                    selected_strategy_id=None,
                    decision_status=StrategyDecisionStatus.ABSTAIN,
                    rationale=(
                        "One safe strategy remains, but explicit decisive evidence and rule "
                        "references are required before recommendation."
                    ),
                    rejected_strategy_ids=rejected_ids,
                    rejection_reasons=rejection_reasons,
                    decisive_evidence=(),
                    decisive_rules=(),
                    unresolved_risks=tuple(
                        dict.fromkeys(
                            (
                                *selected.risks,
                                *selected.unresolved,
                                "Bind decisive evidence and rules before recommendation.",
                            )
                        )
                    ),
                )
            return StrategyDecision(
                selected_strategy_id=selected.strategy_id,
                decision_status=StrategyDecisionStatus.RECOMMENDED,
                rationale=(
                    "Exactly one strategy remains fully verified and deadline-safe, with "
                    "explicit decisive evidence and rule references."
                ),
                rejected_strategy_ids=rejected_ids,
                rejection_reasons=rejection_reasons,
                decisive_evidence=decisive_evidence,
                decisive_rules=decisive_rules,
                unresolved_risks=unresolved_risks,
            )

        status = (
            StrategyDecisionStatus.NEEDS_EVIDENCE
            if uncertainty_seen
            else StrategyDecisionStatus.NO_SAFE_OPTION
        )
        rationale = (
            "No strategy can be recommended until unresolved evidence or verification gaps "
            "are closed."
            if uncertainty_seen
            else "No supplied strategy is both verified and deadline-safe."
        )
        return StrategyDecision(
            selected_strategy_id=None,
            decision_status=status,
            rationale=rationale,
            rejected_strategy_ids=rejected_ids,
            rejection_reasons=rejection_reasons,
            decisive_evidence=(),
            decisive_rules=(),
            unresolved_risks=tuple(
                dict.fromkeys(
                    risk
                    for option in options
                    for risk in (*option.risks, *option.unresolved)
                )
            ),
        )

    @staticmethod
    def _ineligibility_reason(
        *,
        option: StrategyOption,
        remedy_map: dict[str, RemedyOption],
        available_evidence: set[str],
    ) -> tuple[str | None, bool]:
        missing_remedies = tuple(
            remedy_id for remedy_id in option.remedy_ids if remedy_id not in remedy_map
        )
        if missing_remedies:
            return (
                "Missing remedy assessments: " + ", ".join(missing_remedies),
                True,
            )

        remedy_states = tuple(remedy_map[item].admissibility_status for item in option.remedy_ids)
        if any(state is RemedyAdmissibility.NOT_AVAILABLE for state in remedy_states):
            return ("At least one required remedy is not available.", False)
        if any(
            state in {RemedyAdmissibility.UNKNOWN, RemedyAdmissibility.PROVISIONALLY_AVAILABLE}
            for state in remedy_states
        ):
            return ("Required remedy availability is not fully verified.", True)

        missing_evidence = tuple(
            evidence_id
            for evidence_id in option.required_evidence
            if evidence_id not in available_evidence
        )
        if missing_evidence:
            return (
                "Missing required strategy evidence: " + ", ".join(missing_evidence),
                True,
            )
        if option.admissibility is not VerificationLevel.VERIFIED:
            return ("Strategy admissibility is not VERIFIED.", True)
        if option.deadline_safety is DeadlineSafety.UNKNOWN:
            return ("Strategy deadline safety is UNKNOWN.", True)
        if option.deadline_safety is DeadlineSafety.RISK:
            return ("Strategy carries explicit deadline risk.", False)
        if option.unresolved:
            return (
                "Strategy retains unresolved dependencies: " + "; ".join(option.unresolved),
                True,
            )
        return None, False


class FilingTopologyGuard:
    """Convert a selected strategy into an evidence-bound filing topology decision."""

    def decide(
        self,
        *,
        strategy: StrategyOption,
        remedies: tuple[RemedyOption, ...],
        consolidation: ConsolidationAssessment | None = None,
    ) -> FilingTopologyDecision:
        if not strategy.remedy_ids:
            return FilingTopologyDecision(
                status=FilingTopologyStatus.NO_FILING_REQUIRED,
                filing_count=0,
                combined_remedies=(),
                separated_remedies=(),
                rationale="The selected strategy contains no filing remedy.",
                blockers=(),
            )

        remedy_map: dict[str, RemedyOption] = {}
        for remedy in remedies:
            if remedy.remedy_id in remedy_map:
                raise CIRPContractError(f"duplicate remedy_id: {remedy.remedy_id}")
            remedy_map[remedy.remedy_id] = remedy

        selected_ids = tuple(strategy.remedy_ids)
        missing = tuple(item for item in selected_ids if item not in remedy_map)
        if missing:
            return self._uncertain(
                "Selected strategy references missing remedy assessments.",
                ("Assess remedies before filing topology: " + ", ".join(missing),),
            )

        non_verified = tuple(
            item
            for item in selected_ids
            if remedy_map[item].admissibility_status is not RemedyAdmissibility.VERIFIED_AVAILABLE
        )
        if non_verified:
            return self._uncertain(
                "Filing topology cannot be certified from unresolved remedy availability.",
                ("Verify remedy availability: " + ", ".join(non_verified),),
            )

        if len(selected_ids) == 1:
            remedy_id = selected_ids[0]
            return FilingTopologyDecision(
                status=FilingTopologyStatus.SINGLE_FILING_SAFE,
                filing_count=1,
                combined_remedies=(remedy_id,),
                separated_remedies=(),
                rationale="One verified remedy requires one filing topology unit.",
                blockers=(),
            )

        if consolidation is None:
            return self._uncertain(
                "Multiple remedies require an explicit consolidation assessment.",
                ("Verify whether the selected remedies may share filing units.",),
            )

        if set(consolidation.remedy_ids) != set(selected_ids) or len(
            consolidation.remedy_ids
        ) != len(selected_ids):
            return self._uncertain(
                "Consolidation assessment does not cover the exact selected remedy set.",
                ("Reassess consolidation for the exact selected remedies.",),
            )
        if consolidation.status is not ConsolidationAssessmentStatus.VERIFIED:
            blockers = consolidation.blockers or (
                "Resolve consolidation assessment before filing topology.",
            )
            return self._uncertain(consolidation.rationale, blockers)

        route_blockers = self._route_blockers(
            groups=consolidation.remedy_groups,
            remedy_map=remedy_map,
        )
        if route_blockers:
            return self._uncertain(
                "Verified consolidation grouping conflicts with remedy filing routes.",
                route_blockers,
            )

        group_count = len(consolidation.remedy_groups)
        combined = tuple(
            remedy_id
            for group in consolidation.remedy_groups
            if len(group) > 1
            for remedy_id in group
        )
        separated = tuple(
            group[0] for group in consolidation.remedy_groups if len(group) == 1
        )
        if group_count == 1:
            return FilingTopologyDecision(
                status=FilingTopologyStatus.SINGLE_FILING_SAFE,
                filing_count=1,
                combined_remedies=combined or selected_ids,
                separated_remedies=(),
                rationale=consolidation.rationale,
                blockers=(),
            )
        return FilingTopologyDecision(
            status=FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED,
            filing_count=group_count,
            combined_remedies=combined,
            separated_remedies=separated,
            rationale=consolidation.rationale,
            blockers=(),
        )

    @staticmethod
    def _route_blockers(
        *,
        groups: tuple[tuple[str, ...], ...],
        remedy_map: dict[str, RemedyOption],
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        for group in groups:
            if len(group) == 1:
                continue
            routes = {
                (
                    remedy_map[item].target_authority,
                    remedy_map[item].filing_authority,
                    remedy_map[item].filing_via,
                )
                for item in group
            }
            if len(routes) > 1:
                blockers.append(
                    "Consolidation group contains incompatible filing routes: "
                    + ", ".join(group)
                )
        return tuple(blockers)

    @staticmethod
    def _uncertain(rationale: str, blockers: tuple[str, ...]) -> FilingTopologyDecision:
        return FilingTopologyDecision(
            status=FilingTopologyStatus.CONSOLIDATION_UNCERTAIN,
            filing_count=0,
            combined_remedies=(),
            separated_remedies=(),
            rationale=rationale,
            blockers=blockers,
        )