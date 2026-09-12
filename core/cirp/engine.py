"""Canonical end-to-end orchestration for the CIRP Post-v1 Product runtime.

This module composes the already validated CIRP-02..06 components.  It creates no
legal rules, writes no Canonical Case Ledger state and performs no external
submission.  Missing or contradictory material state remains explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

from core.cirp.contracts import (
    CIRPContractError,
    CIRPRunIdentity,
    DeadlineAssessment,
    DocumentAssessment,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    PreflightResult,
    ProceduralAssessment,
    ProceduralRulePack,
    RemedyOption,
    ServiceAssessment,
    ServiceStatus,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyOption,
)
from core.cirp.deadline import (
    DeadlineCalendarProfile,
    DeadlineGuard,
    DeadlineTriggerStatus,
    ExecutableDeadlineRule,
)
from core.cirp.filing import FilingPlanner, FilingSpec
from core.cirp.preflight import FilingExecutionState, HardcorePreflight
from core.cirp.remedy import ExecutableRemedyRule, RemedyApplicabilityStatus, RemedyGuard
from core.cirp.replay import CIRPReplayArtifactRef, CIRPReplayManifest
from core.cirp.report import CIRPReport, CIRPReportBuilder
from core.cirp.strategy import ConsolidationAssessment, FilingTopologyGuard, StrategyGuard
from core.p3.contracts import content_digest


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


def canonical_rule_pack_set_digest(
    rule_packs: tuple[ProceduralRulePack, ...],
) -> str:
    """Digest the exact ordered set of rule-pack identities used by canonical runtime."""

    by_id: dict[str, str] = {}
    for pack in rule_packs:
        if pack.pack_id in by_id:
            raise CIRPContractError(f"duplicate procedural rule pack: {pack.pack_id}")
        by_id[pack.pack_id] = pack.digest()
    return content_digest(
        [
            {"pack_id": pack_id, "digest": by_id[pack_id]}
            for pack_id in sorted(by_id)
        ]
    )


@dataclass(frozen=True, slots=True)
class DeadlineEvaluationRequest:
    rule_pack_id: str
    deadline_id: str
    rule_key: str
    trigger_type: str
    trigger_date: date | None
    trigger_evidence: str | None
    trigger_status: DeadlineTriggerStatus
    effective_law_date: date | None
    safe_buffer_business_days: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("rule_pack_id", "deadline_id", "rule_key", "trigger_type"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.trigger_evidence is not None:
            object.__setattr__(
                self,
                "trigger_evidence",
                _require_nonblank(self.trigger_evidence, field_name="trigger_evidence"),
            )
        if (
            self.safe_buffer_business_days is not None
            and self.safe_buffer_business_days < 0
        ):
            raise CIRPContractError("safe_buffer_business_days cannot be negative")


@dataclass(frozen=True, slots=True)
class RemedyEvaluationRequest:
    rule_pack_id: str
    remedy_id: str
    rule_key: str
    applicability_status: RemedyApplicabilityStatus
    effective_law_date: date | None
    deadline_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("rule_pack_id", "remedy_id", "rule_key"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.deadline_id is not None:
            object.__setattr__(
                self,
                "deadline_id",
                _require_nonblank(self.deadline_id, field_name="deadline_id"),
            )


@dataclass(frozen=True, slots=True)
class CIRPRunRequest:
    run_id: str
    run_identity: CIRPRunIdentity
    document_assessment: DocumentAssessment
    procedural_assessment: ProceduralAssessment
    service_assessment: ServiceAssessment
    rule_packs: tuple[ProceduralRulePack, ...]
    deadline_rules: tuple[ExecutableDeadlineRule, ...]
    deadline_calendars: tuple[DeadlineCalendarProfile, ...]
    remedy_rules: tuple[ExecutableRemedyRule, ...]
    deadline_evaluations: tuple[DeadlineEvaluationRequest, ...]
    remedy_evaluations: tuple[RemedyEvaluationRequest, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]
    strategy_options: tuple[StrategyOption, ...]
    available_evidence_ids: tuple[str, ...]
    decisive_evidence: tuple[str, ...] = ()
    decisive_rules: tuple[str, ...] = ()
    consolidation: ConsolidationAssessment | None = None
    filing_specs: tuple[FilingSpec, ...] = ()
    execution_states: tuple[FilingExecutionState, ...] = ()
    open_questions: tuple[str, ...] = ()
    critical_unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            _require_nonblank(self.run_id, field_name="run_id"),
        )
        for field_name in (
            "available_evidence_ids",
            "decisive_evidence",
            "decisive_rules",
            "open_questions",
            "critical_unknowns",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )


@dataclass(frozen=True, slots=True)
class CIRPRunResult:
    run_identity: CIRPRunIdentity
    deadlines: tuple[DeadlineAssessment, ...]
    remedies: tuple[RemedyOption, ...]
    strategy_decision: StrategyDecision
    filing_topology: FilingTopologyDecision
    filing_plans: tuple[FilingPlan, ...]
    preflights: tuple[PreflightResult, ...]
    report: CIRPReport
    replay_manifest: CIRPReplayManifest


class _DigestibleArtifact(Protocol):
    @property
    def schema(self) -> str: ...

    def digest(self) -> str: ...


class CanonicalCIRPRuntime:
    """One deterministic, fail-closed entry point across CIRP-02..06."""

    def run(self, request: CIRPRunRequest) -> CIRPRunResult:
        self._validate_request_identity(request)
        deadline_guards, remedy_guards = self._build_guards(request)

        deadlines = self._evaluate_deadlines(
            request=request,
            guards=deadline_guards,
        )
        deadline_map = {item.deadline_id: item for item in deadlines}

        remedies = self._evaluate_remedies(
            request=request,
            guards=remedy_guards,
            deadline_map=deadline_map,
        )

        strategy_decision = StrategyGuard().decide(
            options=request.strategy_options,
            remedies=remedies,
            available_evidence_ids=request.available_evidence_ids,
            decisive_evidence=request.decisive_evidence,
            decisive_rules=request.decisive_rules,
        )
        topology = self._topology(
            decision=strategy_decision,
            strategies=request.strategy_options,
            remedies=remedies,
            consolidation=request.consolidation,
        )

        filing_plans: tuple[FilingPlan, ...] = ()
        preflights: tuple[PreflightResult, ...] = ()
        report_open_questions = list(self._open_questions(request, deadlines, remedies, topology))

        if topology.status in {
            FilingTopologyStatus.SINGLE_FILING_SAFE,
            FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED,
        }:
            if request.filing_specs:
                materialized_remedies = self._materialize_filing_remedies(
                    remedies=remedies,
                    requirements=request.evidence_requirements,
                )
                filing_plans = FilingPlanner().plan(
                    strategy_decision=strategy_decision,
                    strategies=request.strategy_options,
                    topology=topology,
                    remedies=materialized_remedies,
                    deadlines=deadlines,
                    available_evidence_ids=request.available_evidence_ids,
                    specs=request.filing_specs,
                )
                preflights = self._preflight(
                    request=request,
                    plans=filing_plans,
                    remedies=materialized_remedies,
                    deadlines=deadlines,
                )
            else:
                report_open_questions.append(
                    "Provide the exact semantic filing specification before execution readiness."
                )
        elif request.filing_specs or request.execution_states:
            raise CIRPContractError(
                "filing specs/execution states are not allowed before an executable filing topology"
            )

        report = CIRPReportBuilder().build(
            case_id=request.run_identity.case_id.value,
            run_id=request.run_id,
            document_summary=self._document_summary(request.document_assessment),
            procedural_summary=self._procedural_summary(request.procedural_assessment),
            deadline_summaries=tuple(self._deadline_summary(item) for item in deadlines),
            remedy_summaries=tuple(self._remedy_summary(item) for item in remedies),
            evidence_requirements=request.evidence_requirements,
            strategy_decision=strategy_decision,
            strategy_summary=strategy_decision.rationale,
            topology=topology,
            filing_plans=filing_plans,
            preflights=preflights,
            open_questions=tuple(dict.fromkeys(report_open_questions)),
            critical_unknowns=self._critical_unknowns(request),
        )
        replay_manifest = self._replay_manifest(
            request=request,
            deadlines=deadlines,
            remedies=remedies,
            strategy_decision=strategy_decision,
            topology=topology,
            filing_plans=filing_plans,
            preflights=preflights,
            report=report,
        )
        return CIRPRunResult(
            run_identity=request.run_identity,
            deadlines=deadlines,
            remedies=remedies,
            strategy_decision=strategy_decision,
            filing_topology=topology,
            filing_plans=filing_plans,
            preflights=preflights,
            report=report,
            replay_manifest=replay_manifest,
        )

    @staticmethod
    def _validate_request_identity(request: CIRPRunRequest) -> None:
        packs = request.rule_packs
        pack_ids = tuple(pack.pack_id for pack in packs)
        if len(pack_ids) != len(set(pack_ids)):
            raise CIRPContractError("rule_packs cannot contain duplicate pack_id values")
        if tuple(sorted(pack_ids)) != tuple(sorted(request.run_identity.rule_pack_ids)):
            raise CIRPContractError(
                "CIRP run rule_pack_ids do not exactly match canonical runtime rule packs"
            )
        expected_digest = canonical_rule_pack_set_digest(packs)
        if request.run_identity.rule_pack_digest != expected_digest:
            raise CIRPContractError(
                "CIRP run rule_pack_digest does not match canonical runtime rule packs"
            )

        available = set(request.available_evidence_ids)
        run_evidence = set(request.run_identity.input_evidence_ids)
        if not available.issubset(run_evidence):
            raise CIRPContractError(
                "available_evidence_ids must be bound to CIRP run input_evidence_ids"
            )

        refs = set(request.document_assessment.evidence_refs)
        refs.add(request.document_assessment.source_evidence_id)
        refs.update(request.procedural_assessment.evidence_refs)
        refs.update(request.service_assessment.evidence_refs)
        for requirement in request.evidence_requirements:
            refs.update(requirement.evidence_refs)
        if request.consolidation is not None:
            refs.update(request.consolidation.evidence_refs)
        if not refs.issubset(run_evidence):
            missing = ", ".join(sorted(refs - run_evidence))
            raise CIRPContractError(
                "CIRP semantic inputs reference evidence outside run identity: " + missing
            )

        if set(request.decisive_evidence) - available:
            raise CIRPContractError(
                "decisive_evidence must be present in available_evidence_ids"
            )

        deadline_ids = tuple(item.deadline_id for item in request.deadline_evaluations)
        if len(deadline_ids) != len(set(deadline_ids)):
            raise CIRPContractError("deadline_evaluations contain duplicate deadline_id values")
        remedy_ids = tuple(item.remedy_id for item in request.remedy_evaluations)
        if len(remedy_ids) != len(set(remedy_ids)):
            raise CIRPContractError("remedy_evaluations contain duplicate remedy_id values")
        requirement_ids = tuple(item.requirement_id for item in request.evidence_requirements)
        if len(requirement_ids) != len(set(requirement_ids)):
            raise CIRPContractError(
                "evidence_requirements contain duplicate requirement_id values"
            )
        strategy_ids = tuple(item.strategy_id for item in request.strategy_options)
        if len(strategy_ids) != len(set(strategy_ids)):
            raise CIRPContractError("strategy_options contain duplicate strategy_id values")
        execution_ids = tuple(item.filing_id for item in request.execution_states)
        if len(execution_ids) != len(set(execution_ids)):
            raise CIRPContractError("execution_states contain duplicate filing_id values")

        for deadline_evaluation in request.deadline_evaluations:
            if deadline_evaluation.rule_pack_id not in set(pack_ids):
                raise CIRPContractError(
                    "deadline evaluation references unknown rule pack: "
                    + deadline_evaluation.rule_pack_id
                )
            if (
                deadline_evaluation.trigger_evidence is not None
                and deadline_evaluation.trigger_evidence not in run_evidence
            ):
                raise CIRPContractError(
                    "deadline trigger evidence is outside run identity: "
                    + deadline_evaluation.trigger_evidence
                )
            CanonicalCIRPRuntime._validate_service_trigger(
                evaluation=deadline_evaluation,
                service=request.service_assessment,
            )
        for remedy_evaluation in request.remedy_evaluations:
            if remedy_evaluation.rule_pack_id not in set(pack_ids):
                raise CIRPContractError(
                    "remedy evaluation references unknown rule pack: "
                    + remedy_evaluation.rule_pack_id
                )

    @staticmethod
    def _validate_service_trigger(
        *,
        evaluation: DeadlineEvaluationRequest,
        service: ServiceAssessment,
    ) -> None:
        if evaluation.trigger_type != "SERVICE_DATE":
            return
        expected_status: DeadlineTriggerStatus
        if service.assessment_status is ServiceStatus.VERIFIED:
            expected_status = DeadlineTriggerStatus.VERIFIED
        elif service.assessment_status in {
            ServiceStatus.USER_REPORTED,
            ServiceStatus.DOCUMENT_STATED,
        }:
            expected_status = DeadlineTriggerStatus.PROVISIONAL
        elif service.assessment_status is ServiceStatus.CONFLICTING:
            expected_status = DeadlineTriggerStatus.CONFLICTING
        else:
            expected_status = DeadlineTriggerStatus.MISSING
        if evaluation.trigger_status is not expected_status:
            raise CIRPContractError(
                "SERVICE_DATE deadline trigger status conflicts with ServiceAssessment"
            )
        if expected_status in {
            DeadlineTriggerStatus.VERIFIED,
            DeadlineTriggerStatus.PROVISIONAL,
        }:
            if evaluation.trigger_date != service.service_date:
                raise CIRPContractError(
                    "SERVICE_DATE trigger date does not match ServiceAssessment"
                )
            if (
                evaluation.trigger_evidence is None
                or evaluation.trigger_evidence not in service.evidence_refs
            ):
                raise CIRPContractError(
                    "SERVICE_DATE trigger evidence is not bound to ServiceAssessment"
                )
        elif evaluation.trigger_date is not None:
            raise CIRPContractError(
                "unsettled SERVICE_DATE assessment cannot supply a settled trigger date"
            )

    @staticmethod
    def _build_guards(
        request: CIRPRunRequest,
    ) -> tuple[dict[str, DeadlineGuard], dict[str, RemedyGuard]]:
        supplied_deadline_tokens = tuple(rule.pack_token for rule in request.deadline_rules)
        supplied_remedy_tokens = tuple(rule.pack_token for rule in request.remedy_rules)
        if len(supplied_deadline_tokens) != len(set(supplied_deadline_tokens)):
            raise CIRPContractError("deadline_rules contain duplicate executable semantics")
        if len(supplied_remedy_tokens) != len(set(supplied_remedy_tokens)):
            raise CIRPContractError("remedy_rules contain duplicate executable semantics")

        deadline_owners: dict[str, str] = {}
        remedy_owners: dict[str, str] = {}
        deadline_guards: dict[str, DeadlineGuard] = {}
        remedy_guards: dict[str, RemedyGuard] = {}

        for pack in request.rule_packs:
            pack_deadline_rules = tuple(
                deadline_rule
                for deadline_rule in request.deadline_rules
                if deadline_rule.pack_token in set(pack.deadline_rules)
            )
            for deadline_rule in pack_deadline_rules:
                previous = deadline_owners.setdefault(deadline_rule.pack_token, pack.pack_id)
                if previous != pack.pack_id:
                    raise CIRPContractError(
                        "deadline rule is bound by multiple packs: "
                        + deadline_rule.pack_token
                    )
            if pack.deadline_rules:
                deadline_guards[pack.pack_id] = DeadlineGuard(
                    rule_pack=pack,
                    rules=pack_deadline_rules,
                    calendars=request.deadline_calendars,
                )

            pack_remedy_rules = tuple(
                remedy_rule
                for remedy_rule in request.remedy_rules
                if remedy_rule.pack_token in set(pack.remedy_rules)
            )
            for remedy_rule in pack_remedy_rules:
                previous = remedy_owners.setdefault(remedy_rule.pack_token, pack.pack_id)
                if previous != pack.pack_id:
                    raise CIRPContractError(
                        "remedy rule is bound by multiple packs: "
                        + remedy_rule.pack_token
                    )
            if pack.remedy_rules:
                remedy_guards[pack.pack_id] = RemedyGuard(
                    rule_pack=pack,
                    rules=pack_remedy_rules,
                )

        if set(deadline_owners) != set(supplied_deadline_tokens):
            raise CIRPContractError(
                "every supplied executable deadline rule must be bound by exactly one rule pack"
            )
        if set(remedy_owners) != set(supplied_remedy_tokens):
            raise CIRPContractError(
                "every supplied executable remedy rule must be bound by exactly one rule pack"
            )

        used_calendar_ids = {
            deadline_rule.calendar_profile_id for deadline_rule in request.deadline_rules
        }
        supplied_calendar_ids = tuple(item.profile_id for item in request.deadline_calendars)
        if len(supplied_calendar_ids) != len(set(supplied_calendar_ids)):
            raise CIRPContractError("deadline_calendars contain duplicate profile_id values")
        if set(supplied_calendar_ids) != used_calendar_ids:
            raise CIRPContractError(
                "deadline_calendars must exactly match executable deadline rule dependencies"
            )
        return deadline_guards, remedy_guards

    @staticmethod
    def _evaluate_deadlines(
        *,
        request: CIRPRunRequest,
        guards: dict[str, DeadlineGuard],
    ) -> tuple[DeadlineAssessment, ...]:
        results: list[DeadlineAssessment] = []
        for evaluation in request.deadline_evaluations:
            guard = guards.get(evaluation.rule_pack_id)
            if guard is None:
                raise CIRPContractError(
                    "deadline evaluation references a rule pack without deadline semantics: "
                    + evaluation.rule_pack_id
                )
            assessment = guard.evaluate(
                deadline_id=evaluation.deadline_id,
                rule_key=evaluation.rule_key,
                trigger_type=evaluation.trigger_type,
                trigger_date=evaluation.trigger_date,
                trigger_evidence=evaluation.trigger_evidence,
                trigger_status=evaluation.trigger_status,
                effective_law_date=evaluation.effective_law_date,
                evaluation_time=request.run_identity.evaluation_time,
                safe_buffer_business_days=evaluation.safe_buffer_business_days,
            )
            if assessment.rule_pack_id != evaluation.rule_pack_id:
                raise CIRPContractError(
                    "deadline assessment escaped its requested rule-pack identity"
                )
            results.append(assessment)
        return tuple(results)

    @staticmethod
    def _evaluate_remedies(
        *,
        request: CIRPRunRequest,
        guards: dict[str, RemedyGuard],
        deadline_map: dict[str, DeadlineAssessment],
    ) -> tuple[RemedyOption, ...]:
        results: list[RemedyOption] = []
        pack_map = {pack.pack_id: pack for pack in request.rule_packs}
        for evaluation in request.remedy_evaluations:
            guard = guards.get(evaluation.rule_pack_id)
            if guard is None:
                raise CIRPContractError(
                    "remedy evaluation references a rule pack without remedy semantics: "
                    + evaluation.rule_pack_id
                )
            deadline = None
            if evaluation.deadline_id is not None:
                deadline = deadline_map.get(evaluation.deadline_id)
                if deadline is None:
                    raise CIRPContractError(
                        "remedy evaluation references missing deadline assessment: "
                        + evaluation.deadline_id
                    )
            option = guard.evaluate(
                remedy_id=evaluation.remedy_id,
                rule_key=evaluation.rule_key,
                applicability_status=evaluation.applicability_status,
                evidence_requirements=request.evidence_requirements,
                effective_law_date=evaluation.effective_law_date,
                deadline=deadline,
            )
            pack = pack_map[evaluation.rule_pack_id]
            if not set(option.applicable_rule_ids).issubset(set(pack.remedy_rules)):
                raise CIRPContractError(
                    "remedy assessment escaped its requested rule-pack identity"
                )
            results.append(option)
        return tuple(results)

    @staticmethod
    def _topology(
        *,
        decision: StrategyDecision,
        strategies: tuple[StrategyOption, ...],
        remedies: tuple[RemedyOption, ...],
        consolidation: ConsolidationAssessment | None,
    ) -> FilingTopologyDecision:
        if decision.decision_status is not StrategyDecisionStatus.RECOMMENDED:
            return FilingTopologyDecision(
                status=FilingTopologyStatus.CONSOLIDATION_UNCERTAIN,
                filing_count=0,
                combined_remedies=(),
                separated_remedies=(),
                rationale=(
                    "Filing topology is withheld until a strategy is RECOMMENDED."
                ),
                blockers=(
                    "Resolve strategy state before filing topology: "
                    + decision.decision_status.value,
                ),
            )
        selected = next(
            (
                option
                for option in strategies
                if option.strategy_id == decision.selected_strategy_id
            ),
            None,
        )
        if selected is None:
            raise CIRPContractError(
                "RECOMMENDED strategy decision does not resolve to a supplied strategy"
            )
        return FilingTopologyGuard().decide(
            strategy=selected,
            remedies=remedies,
            consolidation=consolidation,
        )

    @staticmethod
    def _materialize_filing_remedies(
        *,
        remedies: tuple[RemedyOption, ...],
        requirements: tuple[EvidenceRequirement, ...],
    ) -> tuple[RemedyOption, ...]:
        requirement_map = {item.requirement_id: item for item in requirements}
        materialized: list[RemedyOption] = []
        for remedy in remedies:
            refs: list[str] = []
            unresolved = False
            for requirement_id in remedy.required_evidence:
                requirement = requirement_map.get(requirement_id)
                if requirement is None:
                    unresolved = True
                    break
                if requirement.status is not EvidenceRequirementStatus.PRESENT:
                    unresolved = True
                    break
                refs.extend(requirement.evidence_refs)
            if unresolved:
                materialized.append(remedy)
                continue
            materialized.append(
                replace(
                    remedy,
                    required_evidence=tuple(dict.fromkeys(refs)),
                )
            )
        return tuple(materialized)

    @staticmethod
    def _preflight(
        *,
        request: CIRPRunRequest,
        plans: tuple[FilingPlan, ...],
        remedies: tuple[RemedyOption, ...],
        deadlines: tuple[DeadlineAssessment, ...],
    ) -> tuple[PreflightResult, ...]:
        execution_map = {item.filing_id: item for item in request.execution_states}
        plan_ids = {item.filing_id for item in plans}
        unexpected = set(execution_map) - plan_ids
        if unexpected:
            raise CIRPContractError(
                "execution state has no matching filing plan: "
                + ", ".join(sorted(unexpected))
            )

        results: list[PreflightResult] = []
        for plan in plans:
            execution = execution_map.get(plan.filing_id)
            if execution is None:
                execution = FilingExecutionState(
                    filing_id=plan.filing_id,
                    critical_unknowns=(
                        "Filing execution state has not been established.",
                    ),
                )
            results.append(
                HardcorePreflight().evaluate(
                    plan=plan,
                    remedies=remedies,
                    deadlines=deadlines,
                    available_evidence_ids=request.available_evidence_ids,
                    execution=execution,
                )
            )
        return tuple(results)

    @staticmethod
    def _document_summary(document: DocumentAssessment) -> str:
        label = document.subject or document.document_id
        return f"{document.document_kind.value}: {label}"

    @staticmethod
    def _procedural_summary(procedural: ProceduralAssessment) -> str:
        return (
            f"{procedural.procedure_family}/{procedural.procedural_stage.value}: "
            f"{procedural.procedural_subject}"
        )

    @staticmethod
    def _deadline_summary(deadline: DeadlineAssessment) -> str:
        legal = deadline.legal_deadline.isoformat() if deadline.legal_deadline else "UNKNOWN"
        safe = (
            deadline.safe_internal_deadline.isoformat()
            if deadline.safe_internal_deadline
            else "UNSET"
        )
        return (
            f"{deadline.deadline_id}: {deadline.status.value}; "
            f"legal={legal}; safe={safe}"
        )

    @staticmethod
    def _remedy_summary(remedy: RemedyOption) -> str:
        return f"{remedy.remedy_id}: {remedy.admissibility_status.value}"

    @staticmethod
    def _open_questions(
        request: CIRPRunRequest,
        deadlines: tuple[DeadlineAssessment, ...],
        remedies: tuple[RemedyOption, ...],
        topology: FilingTopologyDecision,
    ) -> tuple[str, ...]:
        items: list[str] = list(request.open_questions)
        items.extend(request.document_assessment.open_questions)
        items.extend(request.procedural_assessment.unresolved)
        for deadline in deadlines:
            items.extend(deadline.blocking_questions)
        for remedy in remedies:
            items.extend(remedy.blockers)
        items.extend(topology.blockers)
        return tuple(dict.fromkeys(items))

    @staticmethod
    def _critical_unknowns(request: CIRPRunRequest) -> tuple[str, ...]:
        items: list[str] = list(request.critical_unknowns)
        for execution in request.execution_states:
            items.extend(execution.critical_unknowns)
        return tuple(dict.fromkeys(items))

    @staticmethod
    def _artifact_ref(
        artifact_id: str,
        artifact: _DigestibleArtifact,
    ) -> CIRPReplayArtifactRef:
        return CIRPReplayArtifactRef(
            artifact_id=artifact_id,
            schema=artifact.schema,
            digest=artifact.digest(),
        )

    @classmethod
    def _replay_manifest(
        cls,
        *,
        request: CIRPRunRequest,
        deadlines: tuple[DeadlineAssessment, ...],
        remedies: tuple[RemedyOption, ...],
        strategy_decision: StrategyDecision,
        topology: FilingTopologyDecision,
        filing_plans: tuple[FilingPlan, ...],
        preflights: tuple[PreflightResult, ...],
        report: CIRPReport,
    ) -> CIRPReplayManifest:
        artifacts: list[CIRPReplayArtifactRef] = [
            cls._artifact_ref("document-assessment", request.document_assessment),
            cls._artifact_ref("procedural-assessment", request.procedural_assessment),
            cls._artifact_ref("service-assessment", request.service_assessment),
        ]
        artifacts.extend(
            cls._artifact_ref(
                f"evidence-requirement:{item.requirement_id}",
                item,
            )
            for item in request.evidence_requirements
        )
        artifacts.extend(
            cls._artifact_ref(f"strategy-option:{item.strategy_id}", item)
            for item in request.strategy_options
        )
        artifacts.extend(
            cls._artifact_ref(f"deadline-assessment:{item.deadline_id}", item)
            for item in deadlines
        )
        artifacts.extend(
            cls._artifact_ref(f"remedy-option:{item.remedy_id}", item)
            for item in remedies
        )
        artifacts.append(cls._artifact_ref("strategy-decision", strategy_decision))
        artifacts.append(cls._artifact_ref("filing-topology", topology))
        artifacts.extend(
            cls._artifact_ref(f"filing-plan:{item.filing_id}", item)
            for item in filing_plans
        )
        artifacts.extend(
            cls._artifact_ref(f"preflight:{item.filing_id}", item)
            for item in preflights
        )
        report_id = f"report:{request.run_id}"
        artifacts.append(cls._artifact_ref(report_id, report))
        return CIRPReplayManifest.build(
            run_identity=request.run_identity,
            artifacts=tuple(artifacts),
            report_artifact_id=report_id,
        )
