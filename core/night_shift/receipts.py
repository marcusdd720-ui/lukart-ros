"""Content-addressed execution receipts for Night Shift closure evidence."""

from __future__ import annotations

from dataclasses import dataclass

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .state_machine import WorkflowPhase, parse_phase


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    task_id: str
    workflow_id: str
    lease_id: str
    fencing_token: int
    policy_digest: str
    decision_digest: str
    state_snapshot_digest: str
    task_capsule_digest: str
    authority_envelope_digest: str
    authority_reservation_digest: str
    environment_digest: str
    verification_digest: str
    input_sha: str
    output_sha: str
    diff_digest: str
    final_state: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "policy_digest",
            "decision_digest",
            "state_snapshot_digest",
            "task_capsule_digest",
            "authority_envelope_digest",
            "authority_reservation_digest",
            "environment_digest",
            "verification_digest",
            "diff_digest",
        ):
            try:
                normalized = require_hex_digest(getattr(self, name), field_name=name)
            except ValueError as exc:
                raise NightShiftContractError(str(exc)) from exc
            object.__setattr__(self, name, normalized)

        for name in ("input_sha", "output_sha"):
            try:
                normalized = require_hex_digest(
                    getattr(self, name),
                    field_name=name,
                    lengths=(40, 64),
                )
            except ValueError as exc:
                raise NightShiftContractError(str(exc)) from exc
            object.__setattr__(self, name, normalized)
        task_id = self.task_id.strip()
        workflow_id = self.workflow_id.strip()
        lease_id = self.lease_id.strip()
        final_state = self.final_state.strip()
        evidence = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if (
            not task_id
            or not workflow_id
            or not lease_id
            or not final_state
            or not evidence
            or any(not item for item in evidence)
        ):
            raise NightShiftContractError("receipt identity/state/evidence must be nonblank")
        if self.fencing_token < 1:
            raise NightShiftContractError("receipt fencing_token must be positive")
        phase = parse_phase(final_state)
        allowed_final = {
            WorkflowPhase.CLOSED_PASS,
            WorkflowPhase.READY_FOR_HUMAN,
            WorkflowPhase.BLOCKED,
            WorkflowPhase.BLOCKED_BY,
            WorkflowPhase.WAITING_EXTERNAL,
            WorkflowPhase.FAILED,
            WorkflowPhase.QUARANTINED,
            WorkflowPhase.SUPERSEDED,
            WorkflowPhase.PAUSED,
        }
        if phase not in allowed_final:
            raise NightShiftContractError(
                "receipt final_state is not a reportable terminal/control phase"
            )
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "lease_id", lease_id)
        object.__setattr__(self, "final_state", phase.value)
        object.__setattr__(self, "evidence_refs", evidence)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "lease_id": self.lease_id,
            "fencing_token": self.fencing_token,
            "policy_digest": self.policy_digest,
            "decision_digest": self.decision_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "authority_envelope_digest": self.authority_envelope_digest,
            "authority_reservation_digest": self.authority_reservation_digest,
            "environment_digest": self.environment_digest,
            "verification_digest": self.verification_digest,
            "input_sha": self.input_sha,
            "output_sha": self.output_sha,
            "diff_digest": self.diff_digest,
            "final_state": self.final_state,
            "evidence_refs": list(self.evidence_refs),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())
