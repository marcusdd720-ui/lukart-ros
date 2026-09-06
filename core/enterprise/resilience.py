"""E9 deterministic resilience/chaos evidence and scale planning."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest
from core.p3.scale import ScaleMeasurement, ScaleProfile, measure_scale_profile

from .contracts import EnterpriseContractError


class FailureClass(StrEnum):
    PROVENANCE_CORRUPTION = "PROVENANCE_CORRUPTION"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    WORKER_CRASH = "WORKER_CRASH"
    API_REPLAY = "API_REPLAY"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    AUTHORIZATION_BYPASS = "AUTHORIZATION_BYPASS"
    ATTESTATION_TAMPER = "ATTESTATION_TAMPER"
    BACKUP_RESTORE = "BACKUP_RESTORE"
    RATE_LIMIT = "RATE_LIMIT"
    SUPPLY_CHAIN_DRIFT = "SUPPLY_CHAIN_DRIFT"


@dataclass(frozen=True, slots=True)
class FailureEvidence:
    failure_class: FailureClass
    passed: bool
    integrity_digest: str
    detail: str

    def digest(self) -> str:
        return content_digest(
            {
                "failure_class": self.failure_class.value,
                "passed": self.passed,
                "integrity_digest": self.integrity_digest,
                "detail": self.detail,
            }
        )


class ResilienceMatrix:
    def __init__(self, evidence: Sequence[FailureEvidence]) -> None:
        ordered = tuple(sorted(evidence, key=lambda item: item.failure_class.value))
        classes = [item.failure_class for item in ordered]
        if len(classes) != len(set(classes)):
            raise EnterpriseContractError("duplicate resilience failure evidence")
        self._evidence = ordered

    @property
    def evidence(self) -> tuple[FailureEvidence, ...]:
        return self._evidence

    def require_coverage(self, required: Sequence[FailureClass]) -> None:
        available = {item.failure_class for item in self._evidence}
        missing = sorted(set(required) - available, key=lambda item: item.value)
        if missing:
            names = ",".join(item.value for item in missing)
            raise EnterpriseContractError(f"resilience coverage missing: {names}")

    @property
    def passed(self) -> bool:
        return bool(self._evidence) and all(item.passed for item in self._evidence)

    def digest(self) -> str:
        return content_digest([item.digest() for item in self._evidence])


@dataclass(frozen=True, slots=True)
class EnterpriseScalePlan:
    fast: ScaleProfile
    certification: ScaleProfile

    def __post_init__(self) -> None:
        if self.fast.evidence_count > self.certification.evidence_count:
            raise EnterpriseContractError("certification scale cannot be smaller than fast scale")
        if self.fast.graph_nodes > self.certification.graph_nodes:
            raise EnterpriseContractError("certification graph cannot be smaller than fast graph")
        if self.certification.evidence_count < 10_000:
            raise EnterpriseContractError("enterprise certification requires >=10k synthetic evidence")
        if self.certification.graph_nodes < 10_000:
            raise EnterpriseContractError("enterprise certification requires >=10k graph nodes")

    @classmethod
    def default(cls) -> EnterpriseScalePlan:
        return cls(
            fast=ScaleProfile(
                name="enterprise-fast",
                evidence_count=256,
                graph_nodes=256,
                replay_count=16,
                concurrency=4,
            ),
            certification=ScaleProfile(
                name="enterprise-certification",
                evidence_count=10_000,
                graph_nodes=10_000,
                replay_count=256,
                concurrency=8,
            ),
        )

    def run_fast(self) -> ScaleMeasurement:
        return measure_scale_profile(self.fast)
