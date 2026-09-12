"""Hardcore fail-closed preflight for CIRP-05 semantic filing plans."""

from __future__ import annotations

from dataclasses import dataclass

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineStatus,
    FilingPlan,
    FilingTopologyStatus,
    PreflightCheck,
    PreflightFinalStatus,
    PreflightResult,
    PreflightSeverity,
    PreflightStatus,
    RemedyAdmissibility,
    RemedyOption,
)


def _unique(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    if any(not value or value != value.strip() for value in values):
        raise CIRPContractError(
            f"{field_name} must contain canonical nonblank values"
        )
    if len(values) != len(set(values)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return values


@dataclass(frozen=True, slots=True)
class FilingExecutionState:
    """Material readiness state that is intentionally separate from the FilingPlan."""

    filing_id: str
    provided_attachments: tuple[str, ...] = ()
    satisfied_formal_requirements: tuple[str, ...] = ()
    signature_ready: bool = False
    copies_ready: bool = False
    critical_unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.filing_id or self.filing_id != self.filing_id.strip():
            raise CIRPContractError("filing_id must be canonical and nonblank")
        for field_name in (
            "provided_attachments",
            "satisfied_formal_requirements",
            "critical_unknowns",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique(getattr(self, field_name), field_name=field_name),
            )


class HardcorePreflight:
    """Evaluate filing readiness without mutating or repairing semantic inputs."""

    def evaluate(
        self,
        *,
        plan: FilingPlan,
        remedies: tuple[RemedyOption, ...],
        deadlines: tuple[DeadlineAssessment, ...],
        available_evidence_ids: tuple[str, ...],
        execution: FilingExecutionState,
    ) -> PreflightResult:
        if execution.filing_id != plan.filing_id:
            raise CIRPContractError(
                "execution state filing_id does not match filing plan"
            )
        remedy_map = self._remedy_map(remedies)
        deadline_map = self._deadline_map(deadlines)
        available_evidence = set(
            _unique(
                available_evidence_ids,
                field_name="available_evidence_ids",
            )
        )

        checks: list[PreflightCheck] = [self._identity_check(plan)]
        selected, selected_error = self._selected_remedies(plan, remedy_map)
        if selected_error is not None:
            checks.append(
                self._check(
                    "remedy-availability",
                    PreflightStatus.FAIL,
                    selected_error,
                )
            )
            selected = ()
        else:
            checks.append(
                self._check(
                    "remedy-availability",
                    PreflightStatus.PASS,
                    "All filing remedies are VERIFIED_AVAILABLE.",
                )
            )

        checks.extend(
            (
                self._route_check(plan, selected),
                self._deadline_check(plan, selected, deadline_map),
                self._semantic_requests_check(plan),
                self._rule_basis_check(plan, selected),
                self._evidence_check(plan, selected, available_evidence),
                self._formal_check(selected, execution),
                self._attachment_check(plan, execution),
                self._signature_check(plan, execution),
                self._copies_check(plan, execution),
                self._topology_check(plan),
                self._unknowns_check(execution),
            )
        )

        critical_unknown = any(
            check.severity is PreflightSeverity.CRITICAL
            and check.status is PreflightStatus.UNKNOWN
            for check in checks
        )
        critical_fail = any(
            check.severity is PreflightSeverity.CRITICAL
            and check.status is PreflightStatus.FAIL
            for check in checks
        )
        blockers = tuple(
            f"{check.check_id}: {check.reason}"
            for check in checks
            if check.severity is PreflightSeverity.CRITICAL
            and check.status in {PreflightStatus.FAIL, PreflightStatus.UNKNOWN}
        )
        if critical_unknown:
            final_status = PreflightFinalStatus.ABSTAIN
        elif critical_fail:
            final_status = PreflightFinalStatus.NOT_READY
        else:
            final_status = PreflightFinalStatus.FILING_READY
        return PreflightResult(
            filing_id=plan.filing_id,
            checks=tuple(checks),
            blockers=blockers,
            warnings=(),
            final_status=final_status,
        )

    @staticmethod
    def _remedy_map(remedies: tuple[RemedyOption, ...]) -> dict[str, RemedyOption]:
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
    def _check(
        check_id: str,
        status: PreflightStatus,
        reason: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> PreflightCheck:
        return PreflightCheck(
            check_id=check_id,
            severity=PreflightSeverity.CRITICAL,
            status=status,
            reason=reason,
            evidence_refs=evidence_refs,
        )

    def _identity_check(self, plan: FilingPlan) -> PreflightCheck:
        if not plan.filing_id or not plan.filing_type:
            return self._check(
                "filing-identity",
                PreflightStatus.FAIL,
                "Filing identity is incomplete.",
            )
        return self._check(
            "filing-identity",
            PreflightStatus.PASS,
            "Filing identity is explicit.",
        )

    @staticmethod
    def _selected_remedies(
        plan: FilingPlan,
        remedy_map: dict[str, RemedyOption],
    ) -> tuple[tuple[RemedyOption, ...], str | None]:
        selected: list[RemedyOption] = []
        for remedy_id in plan.remedy_ids:
            remedy = remedy_map.get(remedy_id)
            if remedy is None:
                return (), f"Missing remedy assessment: {remedy_id}."
            if (
                remedy.admissibility_status
                is not RemedyAdmissibility.VERIFIED_AVAILABLE
            ):
                return (), f"Remedy is not VERIFIED_AVAILABLE: {remedy_id}."
            selected.append(remedy)
        return tuple(selected), None

    def _route_check(
        self,
        plan: FilingPlan,
        selected: tuple[RemedyOption, ...],
    ) -> PreflightCheck:
        if not selected:
            return self._check(
                "filing-route",
                PreflightStatus.FAIL,
                "Verified remedy route is unavailable.",
            )
        expected = {
            (remedy.target_authority, remedy.filing_authority, remedy.filing_via)
            for remedy in selected
        }
        actual = (
            plan.target_authority,
            plan.filing_authority,
            plan.filing_via,
        )
        if len(expected) != 1 or actual not in expected:
            return self._check(
                "filing-route",
                PreflightStatus.FAIL,
                "Filing route does not match verified remedy route.",
            )
        return self._check(
            "filing-route",
            PreflightStatus.PASS,
            "Filing route matches verified remedies.",
        )

    def _deadline_check(
        self,
        plan: FilingPlan,
        selected: tuple[RemedyOption, ...],
        deadline_map: dict[str, DeadlineAssessment],
    ) -> PreflightCheck:
        required_ids = tuple(
            dict.fromkeys(
                remedy.deadline_id
                for remedy in selected
                if remedy.deadline_id is not None
            )
        )
        if not required_ids:
            if plan.deadline_id is not None:
                return self._check(
                    "deadline",
                    PreflightStatus.FAIL,
                    "Plan carries an unexpected deadline identity.",
                )
            return self._check(
                "deadline",
                PreflightStatus.PASS,
                "No deadline dependency applies to the selected remedies.",
            )
        if len(required_ids) != 1 or plan.deadline_id != required_ids[0]:
            return self._check(
                "deadline",
                PreflightStatus.FAIL,
                "Filing deadline identity does not match selected remedies.",
            )
        deadline = deadline_map.get(required_ids[0])
        if deadline is None:
            return self._check(
                "deadline",
                PreflightStatus.UNKNOWN,
                "Required deadline assessment is missing.",
            )
        if deadline.status is DeadlineStatus.EXPIRED:
            return self._check(
                "deadline",
                PreflightStatus.FAIL,
                "Required filing deadline is expired.",
            )
        if deadline.status is not DeadlineStatus.VERIFIED:
            return self._check(
                "deadline",
                PreflightStatus.UNKNOWN,
                "Required filing deadline is not VERIFIED.",
            )
        refs = (
            (deadline.trigger_evidence,)
            if deadline.trigger_evidence is not None
            else ()
        )
        return self._check(
            "deadline",
            PreflightStatus.PASS,
            "Required deadline is VERIFIED.",
            refs,
        )

    def _semantic_requests_check(self, plan: FilingPlan) -> PreflightCheck:
        if not plan.requests or not plan.allegations_or_grounds:
            return self._check(
                "requests-and-grounds",
                PreflightStatus.FAIL,
                "Requests or grounds are missing.",
            )
        return self._check(
            "requests-and-grounds",
            PreflightStatus.PASS,
            "Requests and grounds are explicit.",
        )

    def _rule_basis_check(
        self,
        plan: FilingPlan,
        selected: tuple[RemedyOption, ...],
    ) -> PreflightCheck:
        required = {
            rule
            for remedy in selected
            for rule in remedy.applicable_rule_ids
        }
        if not required.issubset(plan.rule_refs):
            return self._check(
                "rule-basis",
                PreflightStatus.FAIL,
                "Plan does not contain every remedy rule reference.",
            )
        return self._check(
            "rule-basis",
            PreflightStatus.PASS,
            "Rule basis covers selected remedies.",
        )

    def _evidence_check(
        self,
        plan: FilingPlan,
        selected: tuple[RemedyOption, ...],
        available_evidence: set[str],
    ) -> PreflightCheck:
        required = {
            item for remedy in selected for item in remedy.required_evidence
        }
        missing_from_plan = required - set(plan.evidence_refs)
        unavailable = set(plan.evidence_refs) - available_evidence
        if missing_from_plan or unavailable:
            return self._check(
                "evidence-basis",
                PreflightStatus.FAIL,
                "Filing evidence basis is incomplete or unavailable.",
            )
        return self._check(
            "evidence-basis",
            PreflightStatus.PASS,
            "Filing evidence basis is present.",
            plan.evidence_refs,
        )

    def _formal_check(
        self,
        selected: tuple[RemedyOption, ...],
        execution: FilingExecutionState,
    ) -> PreflightCheck:
        required = {
            item for remedy in selected for item in remedy.formal_requirements
        }
        missing = required - set(execution.satisfied_formal_requirements)
        if missing:
            return self._check(
                "formal-requirements",
                PreflightStatus.FAIL,
                "Required formal requirements are not satisfied: "
                + ", ".join(sorted(missing)),
            )
        return self._check(
            "formal-requirements",
            PreflightStatus.PASS,
            "Verified remedy formal requirements are satisfied.",
        )

    def _attachment_check(
        self,
        plan: FilingPlan,
        execution: FilingExecutionState,
    ) -> PreflightCheck:
        missing = set(plan.attachment_requirements) - set(
            execution.provided_attachments
        )
        if missing:
            return self._check(
                "attachments",
                PreflightStatus.FAIL,
                "Required attachments are missing: "
                + ", ".join(sorted(missing)),
            )
        return self._check(
            "attachments",
            PreflightStatus.PASS,
            "Required attachments are present.",
        )

    def _signature_check(
        self,
        plan: FilingPlan,
        execution: FilingExecutionState,
    ) -> PreflightCheck:
        if plan.signature_requirements and not execution.signature_ready:
            return self._check(
                "signature",
                PreflightStatus.FAIL,
                "Signature requirements are not ready.",
            )
        reason = (
            "Signature requirements are ready."
            if plan.signature_requirements
            else "No signature requirement applies."
        )
        return self._check("signature", PreflightStatus.PASS, reason)

    def _copies_check(
        self,
        plan: FilingPlan,
        execution: FilingExecutionState,
    ) -> PreflightCheck:
        if plan.copy_requirements and not execution.copies_ready:
            return self._check(
                "copies",
                PreflightStatus.FAIL,
                "Copy requirements are not ready.",
            )
        reason = (
            "Copy requirements are ready."
            if plan.copy_requirements
            else "No copy requirement applies."
        )
        return self._check("copies", PreflightStatus.PASS, reason)

    def _topology_check(self, plan: FilingPlan) -> PreflightCheck:
        if plan.topology_status not in {
            FilingTopologyStatus.SINGLE_FILING_SAFE,
            FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED,
        }:
            return self._check(
                "topology",
                PreflightStatus.FAIL,
                "Filing topology is not verified for execution.",
            )
        return self._check(
            "topology",
            PreflightStatus.PASS,
            "Filing topology is execution-safe.",
        )

    def _unknowns_check(
        self,
        execution: FilingExecutionState,
    ) -> PreflightCheck:
        if execution.critical_unknowns:
            return self._check(
                "critical-unknowns",
                PreflightStatus.UNKNOWN,
                "Critical UNKNOWN/UNRESOLVED state remains: "
                + "; ".join(execution.critical_unknowns),
            )
        return self._check(
            "critical-unknowns",
            PreflightStatus.PASS,
            "No critical UNKNOWN/UNRESOLVED state remains.",
        )
