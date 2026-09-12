"""Governed canonical CIRP execution and replay binding.

The governance layer verifies existing rule packs before delegating to the
canonical CIRP runtime.  It does not create legal rules, fetch law, mutate case
history, or claim legal certification.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.cirp.contracts import CIRPContractError
from core.cirp.engine import (
    CIRPRunRequest,
    CIRPRunResult,
    CanonicalCIRPRuntime,
    canonical_rule_pack_set_digest,
)
from core.cirp.governance import (
    RulePackFreshnessPolicy,
    RulePackGovernanceReceipt,
    RulePackRegistry,
    verify_rule_pack_governance,
)
from core.p3.contracts import content_digest

GOVERNED_CIRP_REPLAY_SCHEMA_V1 = "lukart.cirp.governed-replay.v1"


def canonical_governance_request_digest(request: CIRPRunRequest) -> str:
    """Digest the request subset that can change legal-rule governance semantics."""

    return content_digest(
        {
            "run_id": request.run_id,
            "run_identity_digest": request.run_identity.digest(),
            "rule_pack_set_digest": canonical_rule_pack_set_digest(request.rule_packs),
            "deadline_evaluations": [
                {
                    "rule_pack_id": item.rule_pack_id,
                    "deadline_id": item.deadline_id,
                    "rule_key": item.rule_key,
                    "trigger_type": item.trigger_type,
                    "trigger_date": item.trigger_date.isoformat() if item.trigger_date else None,
                    "trigger_evidence": item.trigger_evidence,
                    "trigger_status": item.trigger_status.value,
                    "effective_law_date": (
                        item.effective_law_date.isoformat()
                        if item.effective_law_date
                        else None
                    ),
                    "safe_buffer_business_days": item.safe_buffer_business_days,
                }
                for item in request.deadline_evaluations
            ],
            "remedy_evaluations": [
                {
                    "rule_pack_id": item.rule_pack_id,
                    "remedy_id": item.remedy_id,
                    "rule_key": item.rule_key,
                    "applicability_status": item.applicability_status.value,
                    "effective_law_date": (
                        item.effective_law_date.isoformat()
                        if item.effective_law_date
                        else None
                    ),
                    "deadline_id": item.deadline_id,
                }
                for item in request.remedy_evaluations
            ],
        }
    )


@dataclass(frozen=True, slots=True)
class GovernedCIRPReplayManifest:
    canonical_replay_digest: str
    governance_receipt_digest: str
    run_identity_digest: str
    request_digest: str
    schema: str = GOVERNED_CIRP_REPLAY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != GOVERNED_CIRP_REPLAY_SCHEMA_V1:
            raise CIRPContractError("unsupported governed CIRP replay schema")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "canonical_replay_digest": self.canonical_replay_digest,
            "governance_receipt_digest": self.governance_receipt_digest,
            "run_identity_digest": self.run_identity_digest,
            "request_digest": self.request_digest,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class GovernedCIRPRunResult:
    canonical_result: CIRPRunResult
    governance_receipt: RulePackGovernanceReceipt | None
    replay_manifest: GovernedCIRPReplayManifest | None


class GovernedCanonicalCIRPRuntime:
    """Fail-closed rule-pack governance in front of the canonical CIRP runtime."""

    def __init__(
        self,
        *,
        registry: RulePackRegistry | None,
        freshness_policy: RulePackFreshnessPolicy | None,
    ) -> None:
        if (registry is None) != (freshness_policy is None):
            raise CIRPContractError(
                "rule-pack registry and freshness policy must be supplied together"
            )
        self._registry = registry
        self._freshness_policy = freshness_policy
        self._runtime = CanonicalCIRPRuntime()

    def run(self, request: CIRPRunRequest) -> GovernedCIRPRunResult:
        request_digest = canonical_governance_request_digest(request)
        receipt: RulePackGovernanceReceipt | None = None

        if request.rule_packs:
            if self._registry is None or self._freshness_policy is None:
                raise CIRPContractError(
                    "procedural rule packs require registry approval and freshness governance"
                )
            receipt = verify_rule_pack_governance(
                rule_packs=request.rule_packs,
                registry=self._registry,
                freshness_policy=self._freshness_policy,
                evaluation_time=request.run_identity.evaluation_time,
                run_identity_digest=request.run_identity.digest(),
                request_digest=request_digest,
                rule_pack_set_digest=canonical_rule_pack_set_digest(request.rule_packs),
            )
        elif self._registry is not None or self._freshness_policy is not None:
            raise CIRPContractError(
                "rule-pack governance context cannot be attached to a run without rule packs"
            )

        canonical_result = self._runtime.run(request)
        if receipt is None:
            return GovernedCIRPRunResult(
                canonical_result=canonical_result,
                governance_receipt=None,
                replay_manifest=None,
            )

        replay_manifest = GovernedCIRPReplayManifest(
            canonical_replay_digest=canonical_result.replay_manifest.digest(),
            governance_receipt_digest=receipt.digest(),
            run_identity_digest=request.run_identity.digest(),
            request_digest=request_digest,
        )
        return GovernedCIRPRunResult(
            canonical_result=canonical_result,
            governance_receipt=receipt,
            replay_manifest=replay_manifest,
        )
