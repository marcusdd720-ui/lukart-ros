"""Cryptographic runtime binding verification for Night Shift V2-20."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
)
from core.enterprise.contracts import AttestationPurpose
from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .runtime_binding_proposal import (
    BINDING_SIGNATURE_SCHEMA,
    RuntimeBindingProposalResult,
    RuntimeBindingProposalStatus,
    SignedRuntimeBindingProposal,
)


class RuntimeBindingVerificationStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_SHADOW_ACTIVATION_PLAN = "READY_FOR_SHADOW_ACTIVATION_PLAN"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ObservedRuntimeBinding:
    runtime_id: str
    binding_id: str
    proposal_candidate_digest: str
    profile_digest: str
    artifact_digest: str
    registry_snapshot_digest: str
    matrix_snapshot_digest: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        binding_id = self.binding_id.strip()
        if not runtime_id or not binding_id:
            raise NightShiftContractError("observed runtime binding identity is required")
        for name in (
            "proposal_candidate_digest",
            "profile_digest",
            "artifact_digest",
            "registry_snapshot_digest",
            "matrix_snapshot_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError("observed runtime binding requires evidence refs")
        forbidden = ("test:", "synthetic:", "demo:")
        if any(ref.casefold().startswith(forbidden) for ref in refs):
            raise NightShiftContractError(
                "runtime binding verification rejects test/synthetic/demo evidence"
            )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "binding_id", binding_id)
        object.__setattr__(self, "evidence_refs", refs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "binding_id": self.binding_id,
                "proposal_candidate_digest": self.proposal_candidate_digest,
                "profile_digest": self.profile_digest,
                "artifact_digest": self.artifact_digest,
                "registry_snapshot_digest": self.registry_snapshot_digest,
                "matrix_snapshot_digest": self.matrix_snapshot_digest,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeBindingVerificationPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    automatic_registry_mutation_enabled: bool = False
    automatic_matrix_mutation_enabled: bool = False
    automatic_activation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-20 binding verification requires exactly DBOS and Temporal"
            )
        if (
            self.automatic_registry_mutation_enabled
            or self.automatic_matrix_mutation_enabled
            or self.automatic_activation_enabled
        ):
            raise NightShiftContractError(
                "V2-20 cannot mutate registry/matrix or activate a runtime"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "automatic_registry_mutation_enabled": (
                    self.automatic_registry_mutation_enabled
                ),
                "automatic_matrix_mutation_enabled": (
                    self.automatic_matrix_mutation_enabled
                ),
                "automatic_activation_enabled": self.automatic_activation_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeBindingVerificationResult:
    status: RuntimeBindingVerificationStatus
    policy_digest: str
    proposal_digest: str
    signed_proposal_digest: str
    trust_set_digest: str
    signer_identity: str
    signature_verification_digest: str
    observation_digests: tuple[str, ...]
    registry_snapshot_digest: str | None
    matrix_snapshot_digest: str | None
    blockers: tuple[str, ...]
    activation_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.status
            is RuntimeBindingVerificationStatus.READY_FOR_SHADOW_ACTIVATION_PLAN
            and self.blockers
        ):
            raise NightShiftContractError(
                "ready runtime binding verification cannot carry blockers"
            )
        if self.activation_executed:
            raise NightShiftContractError(
                "binding verification cannot activate a runtime"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "proposal_digest": self.proposal_digest,
                "signed_proposal_digest": self.signed_proposal_digest,
                "trust_set_digest": self.trust_set_digest,
                "signer_identity": self.signer_identity,
                "signature_verification_digest": self.signature_verification_digest,
                "observation_digests": list(self.observation_digests),
                "registry_snapshot_digest": self.registry_snapshot_digest,
                "matrix_snapshot_digest": self.matrix_snapshot_digest,
                "blockers": list(self.blockers),
                "activation_executed": self.activation_executed,
            }
        )


def _signature_payload(
    proposal: RuntimeBindingProposalResult,
    *,
    signer_identity: str,
) -> dict[str, object]:
    return {
        "schema": BINDING_SIGNATURE_SCHEMA,
        "artifact": "runtime_binding_proposal",
        "proposal_digest": proposal.digest(),
        "subject_repo_sha": proposal.subject_repo_sha,
        "signer_identity": signer_identity,
    }


def verify_runtime_bindings(
    *,
    proposal: RuntimeBindingProposalResult,
    signed_proposal: SignedRuntimeBindingProposal,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    now_epoch: int,
    observations: tuple[ObservedRuntimeBinding, ...],
    policy: RuntimeBindingVerificationPolicy,
) -> RuntimeBindingVerificationResult:
    blockers: set[str] = set()
    if proposal.status is not RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE:
        blockers.add("BINDING_PROPOSAL_NOT_READY")

    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError("binding verification trust-set identity mismatch")
    if signed_proposal.trust_set_digest != expected:
        raise NightShiftContractError("signed binding trust-set identity mismatch")
    if signed_proposal.proposal_digest != proposal.digest():
        raise NightShiftContractError("signed binding proposal digest mismatch")
    if signed_proposal.attestation.key_id != signed_proposal.signer_identity:
        raise NightShiftContractError("signed binding signer identity mismatch")

    payload = _signature_payload(
        proposal,
        signer_identity=signed_proposal.signer_identity,
    )
    try:
        verifier = CryptoTrustVerifierV1(
            trust_set,
            expected_trust_set_digest=expected,
        )
        verified = verifier.verify(
            signed_proposal.attestation,
            expected_purpose=AttestationPurpose.SECURITY_REVIEW,
            expected_subject_digest=proposal.digest(),
            payload=payload,
            now=now_epoch,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc

    by_candidate = {item.runtime_id: item for item in proposal.candidates}
    by_observed = {item.runtime_id: item for item in observations}
    if len(by_candidate) != len(proposal.candidates):
        raise NightShiftContractError("binding proposal candidates must be unique")
    if len(by_observed) != len(observations):
        raise NightShiftContractError("observed runtime bindings must be unique")
    if tuple(sorted(by_candidate)) != policy.candidate_runtime_ids:
        blockers.add("BINDING_PROPOSAL_CANDIDATES_INCOMPLETE")
    if tuple(sorted(by_observed)) != policy.candidate_runtime_ids:
        blockers.add("OBSERVED_BINDINGS_INCOMPLETE")

    registry_digests = {item.registry_snapshot_digest for item in observations}
    matrix_digests = {item.matrix_snapshot_digest for item in observations}
    if len(registry_digests) != 1:
        blockers.add("REGISTRY_SNAPSHOT_NOT_COHERENT")
    if len(matrix_digests) != 1:
        blockers.add("MATRIX_SNAPSHOT_NOT_COHERENT")

    for runtime_id in policy.candidate_runtime_ids:
        candidate = by_candidate.get(runtime_id)
        observed = by_observed.get(runtime_id)
        if candidate is None or observed is None:
            continue
        if observed.proposal_candidate_digest != candidate.digest():
            raise NightShiftContractError(
                "observed binding proposal candidate digest mismatch"
            )
        if observed.binding_id != candidate.binding_id:
            raise NightShiftContractError("observed binding identity mismatch")
        if observed.profile_digest != candidate.profile_digest:
            raise NightShiftContractError("observed binding profile digest mismatch")
        if observed.artifact_digest != candidate.artifact_digest:
            raise NightShiftContractError("observed binding artifact digest mismatch")

    ordered_blockers = tuple(sorted(blockers))
    return RuntimeBindingVerificationResult(
        status=(
            RuntimeBindingVerificationStatus.READY_FOR_SHADOW_ACTIVATION_PLAN
            if not ordered_blockers
            else RuntimeBindingVerificationStatus.BLOCKED
        ),
        policy_digest=policy.digest(),
        proposal_digest=proposal.digest(),
        signed_proposal_digest=signed_proposal.digest(),
        trust_set_digest=expected,
        signer_identity=signed_proposal.signer_identity,
        signature_verification_digest=verified.verification_digest,
        observation_digests=tuple(sorted(item.digest() for item in observations)),
        registry_snapshot_digest=(
            next(iter(registry_digests)) if len(registry_digests) == 1 else None
        ),
        matrix_snapshot_digest=(
            next(iter(matrix_digests)) if len(matrix_digests) == 1 else None
        ),
        blockers=ordered_blockers,
    )
