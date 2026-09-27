"""Content-addressed execution receipts for Night Shift closure evidence."""

from __future__ import annotations

from dataclasses import dataclass

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    task_id: str
    policy_digest: str
    state_snapshot_digest: str
    task_capsule_digest: str
    authority_envelope_digest: str
    authority_reservation_digest: str
    environment_digest: str
    input_sha: str
    output_sha: str
    diff_digest: str
    final_state: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "policy_digest",
            "state_snapshot_digest",
            "task_capsule_digest",
            "authority_envelope_digest",
            "authority_reservation_digest",
            "environment_digest",
            "input_sha",
            "output_sha",
            "diff_digest",
        ):
            try:
                normalized = require_hex_digest(getattr(self, name), field_name=name)
            except ValueError as exc:
                raise NightShiftContractError(str(exc)) from exc
            object.__setattr__(self, name, normalized)
        task_id = self.task_id.strip()
        final_state = self.final_state.strip()
        evidence = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not task_id or not final_state or not evidence or any(not item for item in evidence):
            raise NightShiftContractError("receipt identity/state/evidence must be nonblank")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "final_state", final_state)
        object.__setattr__(self, "evidence_refs", evidence)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "policy_digest": self.policy_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "authority_envelope_digest": self.authority_envelope_digest,
            "authority_reservation_digest": self.authority_reservation_digest,
            "environment_digest": self.environment_digest,
            "input_sha": self.input_sha,
            "output_sha": self.output_sha,
            "diff_digest": self.diff_digest,
            "final_state": self.final_state,
            "evidence_refs": list(self.evidence_refs),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())
