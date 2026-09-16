"""Fail-closed operational guards for CIRP lifecycle and presentation boundaries.

These guards extend the existing CIRP contracts without becoming a second case-history
store, deadline engine, filing planner, renderer, or strategy engine.  They validate
operational transitions and boundaries only.  Canonical Case Ledger history remains
append-only and authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.cirp.contracts import CIRPContractError, PreflightFinalStatus


class ArtifactLifecycleStatus(StrEnum):
    DRAFT = "DRAFT"
    PREFLIGHTED = "PREFLIGHTED"
    SEND_READY = "SEND_READY"
    APPROVED = "APPROVED"
    SENT_FILED = "SENT/FILED"
    RECEIVED_DELIVERED = "RECEIVED/DELIVERED"
    RESPONDED = "RESPONDED"
    ASSESSED = "ASSESSED"
    CLOSED_ARCHIVED = "CLOSED/ARCHIVED"


@dataclass(frozen=True, slots=True)
class LifecycleTransitionEvidence:
    preflight_executed: bool = False
    preflight_status: PreflightFinalStatus | None = None
    authority_verified: bool = False
    filing_route_verified: bool = False
    no_material_unknowns: bool = False
    explicit_user_authorization: bool = False
    external_action_receipt_verified: bool = False
    delivery_proof_verified: bool = False
    response_evidence_verified: bool = False
    assessment_recorded: bool = False
    closure_recorded: bool = False


_ALLOWED_NEXT: dict[ArtifactLifecycleStatus, ArtifactLifecycleStatus] = {
    ArtifactLifecycleStatus.DRAFT: ArtifactLifecycleStatus.PREFLIGHTED,
    ArtifactLifecycleStatus.PREFLIGHTED: ArtifactLifecycleStatus.SEND_READY,
    ArtifactLifecycleStatus.SEND_READY: ArtifactLifecycleStatus.APPROVED,
    ArtifactLifecycleStatus.APPROVED: ArtifactLifecycleStatus.SENT_FILED,
    ArtifactLifecycleStatus.SENT_FILED: ArtifactLifecycleStatus.RECEIVED_DELIVERED,
    ArtifactLifecycleStatus.RECEIVED_DELIVERED: ArtifactLifecycleStatus.RESPONDED,
    ArtifactLifecycleStatus.RESPONDED: ArtifactLifecycleStatus.ASSESSED,
    ArtifactLifecycleStatus.ASSESSED: ArtifactLifecycleStatus.CLOSED_ARCHIVED,
}


def validate_lifecycle_transition(
    current: ArtifactLifecycleStatus,
    target: ArtifactLifecycleStatus,
    evidence: LifecycleTransitionEvidence,
) -> None:
    """Validate one lifecycle edge; skipping or fabricating evidence fails closed."""

    expected = _ALLOWED_NEXT.get(current)
    if expected is None:
        raise CIRPContractError("closed lifecycle history cannot be advanced or rewritten")
    if target is not expected:
        raise CIRPContractError(
            f"invalid lifecycle transition: {current.value} -> {target.value}"
        )

    if target is ArtifactLifecycleStatus.PREFLIGHTED and not evidence.preflight_executed:
        raise CIRPContractError("PREFLIGHTED requires an executed preflight")
    if target is ArtifactLifecycleStatus.SEND_READY:
        if evidence.preflight_status is not PreflightFinalStatus.FILING_READY:
            raise CIRPContractError("SEND_READY requires FILING_READY preflight status")
        if not evidence.authority_verified:
            raise CIRPContractError("SEND_READY requires verified authority")
        if not evidence.filing_route_verified:
            raise CIRPContractError("SEND_READY requires verified filing route")
        if not evidence.no_material_unknowns:
            raise CIRPContractError("SEND_READY cannot retain material UNKNOWN/UNRESOLVED state")
    if target is ArtifactLifecycleStatus.APPROVED and not evidence.explicit_user_authorization:
        raise CIRPContractError("APPROVED requires explicit user authorization")
    if (
        target is ArtifactLifecycleStatus.SENT_FILED
        and not evidence.external_action_receipt_verified
    ):
        raise CIRPContractError("SENT/FILED requires verified external-action evidence")
    if (
        target is ArtifactLifecycleStatus.RECEIVED_DELIVERED
        and not evidence.delivery_proof_verified
    ):
        raise CIRPContractError("RECEIVED/DELIVERED requires verified delivery proof")
    if target is ArtifactLifecycleStatus.RESPONDED and not evidence.response_evidence_verified:
        raise CIRPContractError("RESPONDED requires response evidence")
    if target is ArtifactLifecycleStatus.ASSESSED and not evidence.assessment_recorded:
        raise CIRPContractError("ASSESSED requires a recorded response assessment")
    if target is ArtifactLifecycleStatus.CLOSED_ARCHIVED and not evidence.closure_recorded:
        raise CIRPContractError("CLOSED/ARCHIVED requires a recorded closure event")


def append_lifecycle_transition(
    history: tuple[ArtifactLifecycleStatus, ...],
    target: ArtifactLifecycleStatus,
    evidence: LifecycleTransitionEvidence,
) -> tuple[ArtifactLifecycleStatus, ...]:
    """Return a new append-only history after validating the next transition."""

    if not history:
        raise CIRPContractError("lifecycle history requires an existing DRAFT state")
    if history[0] is not ArtifactLifecycleStatus.DRAFT:
        raise CIRPContractError("lifecycle history must begin at DRAFT")
    validate_lifecycle_transition(history[-1], target, evidence)
    return (*history, target)


def begin_reopened_run(
    closed_history: tuple[ArtifactLifecycleStatus, ...],
    *,
    material_evidence_ids: tuple[str, ...],
) -> tuple[ArtifactLifecycleStatus, ...]:
    """Start a new run after closure without rewriting the historical closed run."""

    if not closed_history or closed_history[-1] is not ArtifactLifecycleStatus.CLOSED_ARCHIVED:
        raise CIRPContractError("reopen requires an existing CLOSED/ARCHIVED history")
    if not material_evidence_ids:
        raise CIRPContractError("reopen requires new material evidence")
    if any(not item or item != item.strip() for item in material_evidence_ids):
        raise CIRPContractError("material evidence ids must be canonical and nonblank")
    if len(material_evidence_ids) != len(set(material_evidence_ids)):
        raise CIRPContractError("material evidence ids cannot contain duplicates")
    return (ArtifactLifecycleStatus.DRAFT,)


def assert_legal_effect_claim(*, legal_effect_verified: bool) -> None:
    """Delivery alone is never sufficient proof of a legal effect."""

    if not legal_effect_verified:
        raise CIRPContractError("legal effect cannot be claimed without independent verification")


@dataclass(frozen=True, slots=True)
class RendererSemanticInput:
    semantic_digest: str
    filing_plan_digest: str
    strategy_digest: str
    evidence_digest: str
    unresolved_markers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RendererSemanticOutput:
    semantic_digest: str
    filing_plan_digest: str
    strategy_digest: str
    evidence_digest: str
    unresolved_markers: tuple[str, ...] = ()
    invented_fields: tuple[str, ...] = ()
    critical_placeholders: tuple[str, ...] = ()
    presentation_digest: str | None = None


def validate_renderer_boundary(
    source: RendererSemanticInput,
    rendered: RendererSemanticOutput,
    *,
    send_ready: bool,
) -> None:
    """Ensure presentation work cannot mutate or invent case semantics."""

    for field_name in (
        "semantic_digest",
        "filing_plan_digest",
        "strategy_digest",
        "evidence_digest",
    ):
        if getattr(source, field_name) != getattr(rendered, field_name):
            raise CIRPContractError(f"renderer changed semantic field: {field_name}")
    if rendered.invented_fields:
        raise CIRPContractError("renderer cannot invent factual or identifying fields")
    if rendered.unresolved_markers != source.unresolved_markers:
        raise CIRPContractError("renderer cannot hide or rewrite UNKNOWN/UNRESOLVED state")
    if send_ready and rendered.critical_placeholders:
        raise CIRPContractError("SEND_READY rendering cannot retain critical placeholders")


class RedTeamFindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RedTeamFinding:
    finding_id: str
    status: RedTeamFindingStatus
    reason: str

    def __post_init__(self) -> None:
        if not self.finding_id or self.finding_id != self.finding_id.strip():
            raise CIRPContractError("red-team finding_id must be canonical and nonblank")
        if not self.reason or self.reason != self.reason.strip():
            raise CIRPContractError("red-team reason must be canonical and nonblank")


def red_team_downstream_status(
    findings: tuple[RedTeamFinding, ...],
    *,
    preflight_status: PreflightFinalStatus,
) -> PreflightFinalStatus:
    """Propagate adversarial findings into the downstream filing-readiness gate."""

    if any(item.status is RedTeamFindingStatus.UNKNOWN for item in findings):
        return PreflightFinalStatus.ABSTAIN
    if any(item.status is RedTeamFindingStatus.FAIL for item in findings):
        return PreflightFinalStatus.NOT_READY
    return preflight_status


def assert_public_surface_canary_clean(
    *,
    private_canaries: tuple[str, ...],
    public_values: tuple[str, ...],
) -> None:
    """Fail closed if any synthetic private canary reaches a public-facing surface."""

    if any(not marker or marker != marker.strip() for marker in private_canaries):
        raise CIRPContractError("private canaries must be canonical and nonblank")
    for marker in private_canaries:
        if any(marker in value for value in public_values):
            raise CIRPContractError("private CASE canary leaked to a public surface")
