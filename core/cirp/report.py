"""Render-neutral CIRP case report for CIRP-05.

The report is a deterministic projection of already-derived CIRP artifacts. It
cannot silently repair, suppress or promote UNKNOWN/UNRESOLVED state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.cirp.contracts import (
    CIRPContractError,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    PreflightFinalStatus,
    PreflightResult,
    StrategyDecision,
    StrategyDecisionStatus,
)
from core.p3.contracts import canonical_json, content_digest

CIRP_REPORT_SCHEMA_V1 = "lukart.cirp.report.v1"


class CIRPReportStatus(StrEnum):
    READY_TO_FILE = "READY_TO_FILE"
    NOT_READY = "NOT_READY"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    NO_SAFE_OPTION = "NO_SAFE_OPTION"
    NO_FILING_REQUIRED = "NO_FILING_REQUIRED"
    ABSTAIN = "ABSTAIN"


def _unique(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    if any(not value or value != value.strip() for value in values):
        raise CIRPContractError(f"{field_name} must contain canonical nonblank values")
    if len(values) != len(set(values)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return values


@dataclass(frozen=True, slots=True)
class CIRPReport:
    case_id: str
    run_id: str
    document_summary: str
    procedural_summary: str
    deadline_summaries: tuple[str, ...]
    remedy_summaries: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    strategy_status: str
    strategy_summary: str
    filing_topology_status: str
    filing_ids: tuple[str, ...]
    preflight_statuses: tuple[str, ...]
    open_questions: tuple[str, ...]
    critical_unknowns: tuple[str, ...]
    status: CIRPReportStatus
    schema: str = CIRP_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CIRP_REPORT_SCHEMA_V1:
            raise CIRPContractError("unsupported CIRP report schema")
        for field_name in (
            "case_id",
            "run_id",
            "document_summary",
            "procedural_summary",
            "strategy_status",
            "strategy_summary",
            "filing_topology_status",
        ):
            value = getattr(self, field_name)
            if not value or value != value.strip():
                raise CIRPContractError(f"{field_name} must be canonical and nonblank")
        for field_name in (
            "deadline_summaries",
            "remedy_summaries",
            "evidence_gaps",
            "filing_ids",
            "preflight_statuses",
            "open_questions",
            "critical_unknowns",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique(getattr(self, field_name), field_name=field_name),
            )
        if self.critical_unknowns and self.status is CIRPReportStatus.READY_TO_FILE:
            raise CIRPContractError("READY_TO_FILE report cannot hide critical unknowns")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "document_summary": self.document_summary,
            "procedural_summary": self.procedural_summary,
            "deadline_summaries": list(self.deadline_summaries),
            "remedy_summaries": list(self.remedy_summaries),
            "evidence_gaps": list(self.evidence_gaps),
            "strategy_status": self.strategy_status,
            "strategy_summary": self.strategy_summary,
            "filing_topology_status": self.filing_topology_status,
            "filing_ids": list(self.filing_ids),
            "preflight_statuses": list(self.preflight_statuses),
            "open_questions": list(self.open_questions),
            "critical_unknowns": list(self.critical_unknowns),
            "status": self.status.value,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.canonical_dict())

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class CIRPReportBuilder:
    """Project runtime artifacts into one truthful operator-facing report model."""

    def build(
        self,
        *,
        case_id: str,
        run_id: str,
        document_summary: str,
        procedural_summary: str,
        deadline_summaries: tuple[str, ...],
        remedy_summaries: tuple[str, ...],
        evidence_requirements: tuple[EvidenceRequirement, ...],
        strategy_decision: StrategyDecision,
        strategy_summary: str,
        topology: FilingTopologyDecision,
        filing_plans: tuple[FilingPlan, ...],
        preflights: tuple[PreflightResult, ...],
        open_questions: tuple[str, ...] = (),
        critical_unknowns: tuple[str, ...] = (),
    ) -> CIRPReport:
        filing_ids = tuple(plan.filing_id for plan in filing_plans)
        if len(filing_ids) != len(set(filing_ids)):
            raise CIRPContractError("report filing plans contain duplicate filing_id values")
        preflight_ids = tuple(result.filing_id for result in preflights)
        if len(preflight_ids) != len(set(preflight_ids)):
            raise CIRPContractError("report preflight results contain duplicate filing_id values")
        if set(preflight_ids) != set(filing_ids):
            raise CIRPContractError("report requires one preflight result per filing plan")

        evidence_gaps = tuple(
            requirement.requirement_id
            for requirement in evidence_requirements
            if requirement.status
            in {
                EvidenceRequirementStatus.MISSING,
                EvidenceRequirementStatus.CONFLICTING,
                EvidenceRequirementStatus.STALE,
                EvidenceRequirementStatus.UNVERIFIED,
            }
        )
        critical_unknowns = _unique(critical_unknowns, field_name="critical_unknowns")
        open_questions = _unique(open_questions, field_name="open_questions")
        status = self._status(
            strategy_decision=strategy_decision,
            topology=topology,
            preflights=preflights,
            evidence_gaps=evidence_gaps,
            critical_unknowns=critical_unknowns,
        )
        return CIRPReport(
            case_id=case_id,
            run_id=run_id,
            document_summary=document_summary,
            procedural_summary=procedural_summary,
            deadline_summaries=deadline_summaries,
            remedy_summaries=remedy_summaries,
            evidence_gaps=evidence_gaps,
            strategy_status=strategy_decision.decision_status.value,
            strategy_summary=strategy_summary,
            filing_topology_status=topology.status.value,
            filing_ids=filing_ids,
            preflight_statuses=tuple(
                f"{result.filing_id}:{result.final_status.value}" for result in preflights
            ),
            open_questions=open_questions,
            critical_unknowns=critical_unknowns,
            status=status,
        )

    @staticmethod
    def _status(
        *,
        strategy_decision: StrategyDecision,
        topology: FilingTopologyDecision,
        preflights: tuple[PreflightResult, ...],
        evidence_gaps: tuple[str, ...],
        critical_unknowns: tuple[str, ...],
    ) -> CIRPReportStatus:
        if critical_unknowns:
            return CIRPReportStatus.ABSTAIN
        if strategy_decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE:
            return CIRPReportStatus.NEEDS_EVIDENCE
        if strategy_decision.decision_status is StrategyDecisionStatus.DECISION_REQUIRED:
            return CIRPReportStatus.DECISION_REQUIRED
        if strategy_decision.decision_status is StrategyDecisionStatus.NO_SAFE_OPTION:
            return CIRPReportStatus.NO_SAFE_OPTION
        if strategy_decision.decision_status is StrategyDecisionStatus.ABSTAIN:
            return CIRPReportStatus.ABSTAIN
        if evidence_gaps:
            return CIRPReportStatus.NEEDS_EVIDENCE
        if topology.status is FilingTopologyStatus.NO_FILING_REQUIRED:
            return CIRPReportStatus.NO_FILING_REQUIRED
        if topology.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN:
            return CIRPReportStatus.ABSTAIN
        if not preflights:
            return CIRPReportStatus.NOT_READY
        if any(result.final_status is PreflightFinalStatus.ABSTAIN for result in preflights):
            return CIRPReportStatus.ABSTAIN
        if any(
            result.final_status is not PreflightFinalStatus.FILING_READY
            for result in preflights
        ):
            return CIRPReportStatus.NOT_READY
        return CIRPReportStatus.READY_TO_FILE
