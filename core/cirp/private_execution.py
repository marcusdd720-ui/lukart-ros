"""One-step private-case execution over the existing CIRP Product surfaces.

This module composes the verified private-evidence intake adapter with the governed
canonical CIRP runtime. It does not read plaintext evidence directly, persist case
history, create legal rules, render filings, or submit anything externally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.case_ledger.contracts import LedgerEvent
from core.cirp.contracts import CIRPContractError
from core.cirp.engine import CIRPRunRequest
from core.cirp.governance import RulePackFreshnessPolicy, RulePackRegistry
from core.cirp.governed_runtime import GovernedCIRPRunResult, GovernedCanonicalCIRPRuntime
from core.cirp.intake import bind_private_case_request
from core.p3.contracts import P3ContractError, content_digest, require_hex_digest
from core.private_evidence_v1 import PrivateEvidenceStore

PRIVATE_CIRP_EXECUTION_SCHEMA_V1 = "lukart.cirp.private-execution.v1"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except P3ContractError as exc:
        raise CIRPContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class PrivateCIRPExecutionReceipt:
    """Privacy-minimized proof that one private CIRP execution completed.

    The receipt contains only content digests and no case identifier, document name,
    source text, party name, case number, filing payload, or evidence body.
    """

    run_identity_digest: str
    report_digest: str
    canonical_replay_digest: str
    governance_receipt_digest: str | None
    governed_replay_digest: str | None
    schema: str = PRIVATE_CIRP_EXECUTION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PRIVATE_CIRP_EXECUTION_SCHEMA_V1:
            raise CIRPContractError("unsupported private CIRP execution schema")
        for field_name in (
            "run_identity_digest",
            "report_digest",
            "canonical_replay_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        if (self.governance_receipt_digest is None) != (self.governed_replay_digest is None):
            raise CIRPContractError(
                "governance receipt and governed replay digests must be present together"
            )
        for field_name in ("governance_receipt_digest", "governed_replay_digest"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _digest(value, field_name=field_name),
                )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_identity_digest": self.run_identity_digest,
            "report_digest": self.report_digest,
            "canonical_replay_digest": self.canonical_replay_digest,
            "governance_receipt_digest": self.governance_receipt_digest,
            "governed_replay_digest": self.governed_replay_digest,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class PrivateCIRPExecutionResult:
    """Local execution result plus a privacy-minimized execution receipt."""

    governed_result: GovernedCIRPRunResult
    receipt: PrivateCIRPExecutionReceipt


def run_private_case(
    store: PrivateEvidenceStore,
    request: CIRPRunRequest,
    *,
    document_ids: tuple[str, ...],
    policy_identity: str,
    runtime_identity: str,
    evaluation_time: datetime,
    source_configuration_digest: str,
    registry: RulePackRegistry | None,
    freshness_policy: RulePackFreshnessPolicy | None,
    input_events: tuple[LedgerEvent, ...] = (),
    model_identity: str | None = None,
) -> PrivateCIRPExecutionResult:
    """Bind verified private evidence and execute CIRP through one fail-closed call.

    Rule-pack governance remains mandatory whenever the request contains rule packs;
    the governed runtime enforces that boundary. No result is persisted by this
    function and no external filing side effect exists here.
    """

    bound_request = bind_private_case_request(
        store,
        request,
        document_ids=document_ids,
        policy_identity=policy_identity,
        runtime_identity=runtime_identity,
        evaluation_time=evaluation_time,
        source_configuration_digest=source_configuration_digest,
        input_events=input_events,
        model_identity=model_identity,
    )
    governed_result = GovernedCanonicalCIRPRuntime(
        registry=registry,
        freshness_policy=freshness_policy,
    ).run(bound_request)

    canonical_result = governed_result.canonical_result
    run_identity_digest = bound_request.run_identity.digest()
    if canonical_result.run_identity.digest() != run_identity_digest:
        raise CIRPContractError("private CIRP execution escaped its bound run identity")

    governance_receipt_digest = (
        governed_result.governance_receipt.digest()
        if governed_result.governance_receipt is not None
        else None
    )
    governed_replay_digest = (
        governed_result.replay_manifest.digest()
        if governed_result.replay_manifest is not None
        else None
    )
    receipt = PrivateCIRPExecutionReceipt(
        run_identity_digest=run_identity_digest,
        report_digest=canonical_result.report.digest(),
        canonical_replay_digest=canonical_result.replay_manifest.digest(),
        governance_receipt_digest=governance_receipt_digest,
        governed_replay_digest=governed_replay_digest,
    )
    return PrivateCIRPExecutionResult(
        governed_result=governed_result,
        receipt=receipt,
    )
