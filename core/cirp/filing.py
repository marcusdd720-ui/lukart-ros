"""Semantic filing planning for CIRP-05.

The planner converts a RECOMMENDED strategy plus a verified filing topology into
immutable ``FilingPlan`` contracts. It does not render DOCX/PDF and it never
transmits a filing. All case-specific content is supplied by the caller and must
remain evidence/rule bound.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    RemedyAdmissibility,
    RemedyOption,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyOption,
)


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _unique_nonblank(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(
        _require_nonblank(item, field_name=field_name) for item in values
    )
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class FilingSpec:
    """Caller-supplied semantic content for exactly one filing unit."""

    filing_id: str
    filing_type: str
    remedy_ids: tuple[str, ...]
    requests: tuple[str, ...]
    allegations_or_grounds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rule_refs: tuple[str, ...]
    attachment_requirements: tuple[str, ...]
    signature_requirements: tuple[str, ...]
    copy_requirements: tuple[str, ...]
    delivery_method: str

    def __post_init__(self) -> None:
        for field_name in ("filing_id", "filing_type", "delivery_method"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )
        for field_name in (
            "remedy_ids",
            "requests",
            "allegations_or_grounds",
            "evidence_refs",
            "rule_refs",
            "attachment_requirements",
            "signature_requirements",
            "copy_requirements",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )
        if not self.remedy_ids:
            raise CIRPContractError("filing spec requires remedy_ids")
        if not self.requests:
            raise CIRPContractError("filing spec requires at least one request")
        if not self.allegations_or_grounds:
            raise CIRPContractError(
                "filing spec requires allegations_or_grounds"
            )


class FilingPlanner:
    """Build a complete, exact and fail-closed semantic filing set."""

    def plan(
        self,
        *,
        strategy_decision: StrategyDecision,
        strategies: tuple[StrategyOption, ...],
        topology: FilingTopologyDecision,
        remedies: tuple[RemedyOption, ...],
        deadlines: tuple[DeadlineAssessment, ...],
        available_evidence_ids: tuple[str, ...],
        specs: tuple[FilingSpec, ...],
    ) -> tuple[FilingPlan, ...]:
        selected = self._selected_strategy(strategy_decision, strategies)
        if topology.status in {
            FilingTopologyStatus.CONSOLIDATION_UNCERTAIN,
            FilingTopologyStatus.NO_FILING_REQUIRED,
        }:
            raise CIRPContractError(
                "cannot build filing plans from topology "
                f"{topology.status.value}"
            )
        self._validate_partition(selected, topology, specs)

        remedy_map = self._remedy_map(remedies)
        deadline_map = self._deadline_map(deadlines)
        available_evidence = set(
            _unique_nonblank(
                available_evidence_ids,
                field_name="available_evidence_ids",
            )
        )

        plans: list[FilingPlan] = []
        for spec in specs:
            selected_remedies = tuple(
                self._verified_remedy(remedy_id, remedy_map)
                for remedy_id in spec.remedy_ids
            )
            self._validate_route(selected_remedies)
            self._validate_basis(
                spec=spec,
                remedies=selected_remedies,
                deadlines=deadline_map,
                available_evidence=available_evidence,
            )
            first = selected_remedies[0]
            deadline_ids = tuple(
                dict.fromkeys(
                    remedy.deadline_id
                    for remedy in selected_remedies
                    if remedy.deadline_id is not None
                )
            )
            deadline_id = deadline_ids[0] if len(deadline_ids) == 1 else None
            if len(deadline_ids) > 1:
                raise CIRPContractError(
                    "one filing unit cannot contain remedies with different "
                    "deadline identities"
                )
            plans.append(
                FilingPlan(
                    filing_id=spec.filing_id,
                    filing_type=spec.filing_type,
                    target_authority=first.target_authority,
                    filing_authority=first.filing_authority,
                    filing_via=first.filing_via,
                    objective=selected.objective,
                    requests=spec.requests,
                    allegations_or_grounds=spec.allegations_or_grounds,
                    remedy_ids=spec.remedy_ids,
                    rule_refs=spec.rule_refs,
                    evidence_refs=spec.evidence_refs,
                    attachment_requirements=spec.attachment_requirements,
                    signature_requirements=spec.signature_requirements,
                    copy_requirements=spec.copy_requirements,
                    deadline_id=deadline_id,
                    delivery_method=spec.delivery_method,
                    topology_status=topology.status,
                )
            )
        return tuple(plans)

    @staticmethod
    def _selected_strategy(
        decision: StrategyDecision,
        strategies: tuple[StrategyOption, ...],
    ) -> StrategyOption:
        if decision.decision_status is not StrategyDecisionStatus.RECOMMENDED:
            raise CIRPContractError(
                "filing planning requires a RECOMMENDED strategy"
            )
        strategy_map: dict[str, StrategyOption] = {}
        for strategy in strategies:
            if strategy.strategy_id in strategy_map:
                raise CIRPContractError(
                    f"duplicate strategy_id: {strategy.strategy_id}"
                )
            strategy_map[strategy.strategy_id] = strategy
        if decision.selected_strategy_id not in strategy_map:
            raise CIRPContractError(
                "selected strategy is not present in supplied strategies"
            )
        return strategy_map[decision.selected_strategy_id]

    @staticmethod
    def _remedy_map(
        remedies: tuple[RemedyOption, ...],
    ) -> dict[str, RemedyOption]:
        result: dict[str, RemedyOption] = {}
        for remedy in remedies:
            if remedy.remedy_id in result:
                raise CIRPContractError(
                    f"duplicate remedy_id: {remedy.remedy_id}"
                )
            result[remedy.remedy_id] = remedy
        return result

    @staticmethod
    def _deadline_map(
        deadlines: tuple[DeadlineAssessment, ...],
    ) -> dict[str, DeadlineAssessment]:
        result: dict[str, DeadlineAssessment] = {}
        for deadline in deadlines:
            if deadline.deadline_id in result:
                raise CIRPContractError(
                    f"duplicate deadline_id: {deadline.deadline_id}"
                )
            result[deadline.deadline_id] = deadline
        return result

    @staticmethod
    def _verified_remedy(
        remedy_id: str,
        remedy_map: dict[str, RemedyOption],
    ) -> RemedyOption:
        remedy = remedy_map.get(remedy_id)
        if remedy is None:
            raise CIRPContractError(
                f"missing remedy assessment: {remedy_id}"
            )
        if (
            remedy.admissibility_status
            is not RemedyAdmissibility.VERIFIED_AVAILABLE
        ):
            raise CIRPContractError(
                f"remedy is not VERIFIED_AVAILABLE: {remedy_id}"
            )
        return remedy

    @staticmethod
    def _validate_partition(
        strategy: StrategyOption,
        topology: FilingTopologyDecision,
        specs: tuple[FilingSpec, ...],
    ) -> None:
        if len(specs) != topology.filing_count:
            raise CIRPContractError(
                "filing spec count does not match topology filing_count"
            )
        filing_ids = tuple(spec.filing_id for spec in specs)
        if len(filing_ids) != len(set(filing_ids)):
            raise CIRPContractError(
                "filing specs cannot contain duplicate filing_id values"
            )
        flattened = tuple(
            remedy_id
            for spec in specs
            for remedy_id in spec.remedy_ids
        )
        if len(flattened) != len(set(flattened)):
            raise CIRPContractError(
                "a remedy cannot occur in more than one filing spec"
            )
        if (
            set(flattened) != set(strategy.remedy_ids)
            or len(flattened) != len(strategy.remedy_ids)
        ):
            raise CIRPContractError(
                "filing specs must exactly partition selected strategy remedies"
            )
        if topology.status is FilingTopologyStatus.SINGLE_FILING_SAFE:
            if (
                len(specs) != 1
                or set(specs[0].remedy_ids) != set(strategy.remedy_ids)
            ):
                raise CIRPContractError(
                    "SINGLE_FILING_SAFE requires one exact filing unit"
                )
        if topology.status is FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED:
            combined = {
                remedy_id
                for spec in specs
                if len(spec.remedy_ids) > 1
                for remedy_id in spec.remedy_ids
            }
            separated = {
                spec.remedy_ids[0]
                for spec in specs
                if len(spec.remedy_ids) == 1
            }
            if combined != set(topology.combined_remedies):
                raise CIRPContractError(
                    "filing specs do not match topology combined_remedies"
                )
            if separated != set(topology.separated_remedies):
                raise CIRPContractError(
                    "filing specs do not match topology separated_remedies"
                )

    @staticmethod
    def _validate_route(remedies: tuple[RemedyOption, ...]) -> None:
        routes = {
            (
                remedy.target_authority,
                remedy.filing_authority,
                remedy.filing_via,
            )
            for remedy in remedies
        }
        if len(routes) != 1:
            raise CIRPContractError(
                "filing unit contains incompatible remedy routes"
            )

    @staticmethod
    def _validate_basis(
        *,
        spec: FilingSpec,
        remedies: tuple[RemedyOption, ...],
        deadlines: dict[str, DeadlineAssessment],
        available_evidence: set[str],
    ) -> None:
        required_rules = {
            rule
            for remedy in remedies
            for rule in remedy.applicable_rule_ids
        }
        if not required_rules.issubset(spec.rule_refs):
            raise CIRPContractError(
                "filing spec is missing remedy rule references"
            )
        required_evidence = {
            item for remedy in remedies for item in remedy.required_evidence
        }
        if not required_evidence.issubset(spec.evidence_refs):
            raise CIRPContractError(
                "filing spec is missing remedy evidence references"
            )
        if not set(spec.evidence_refs).issubset(available_evidence):
            raise CIRPContractError(
                "filing spec references unavailable evidence"
            )
        for remedy in remedies:
            if remedy.deadline_id is None:
                continue
            deadline = deadlines.get(remedy.deadline_id)
            if deadline is None:
                raise CIRPContractError(
                    f"missing deadline assessment: {remedy.deadline_id}"
                )
            if deadline.status is not DeadlineStatus.VERIFIED:
                raise CIRPContractError(
                    "filing planning requires VERIFIED deadline: "
                    f"{remedy.deadline_id}"
                )
