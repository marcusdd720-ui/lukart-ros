"""Fail-closed runtime binding proposal for Night Shift V2-19."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoTrustSetV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import (
    AttestationPurpose,
    AttestationSigner,
    SignedAttestation,
)
from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .runtime_adapter_admission import (
    RuntimeAdapterAdmissionResult,
    RuntimeAdapterAdmissionStatus,
)
from .runtime_profiles import RuntimeProfile

BINDING_SIGNATURE_SCHEMA = "night-shift-runtime-binding-signature/v1"


class RuntimeBindingProposalStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN_SIGNATURE = "READY_FOR_HUMAN_SIGNATURE"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


def _git_sha(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if re.fullmatch(r"[0-9a-f]{40}", normalized) is None:
        raise NightShiftContractError(
            f"{field_name} must be a lowercase 40-character Git SHA"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class RuntimeBindingProposalPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    automatic_registry_mutation_enabled: bool = False
    automatic_matrix_mutation_enabled: bool = False
    automatic_activation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-19 binding proposal requires exactly DBOS and Temporal"
            )
        if (
            self.automatic_registry_mutation_enabled
            or self.automatic_matrix_mutation_enabled
            or self.automatic_activation_enabled
        ):
            raise NightShiftContractError(
                "V2-19 cannot mutate registry/matrix or activate a runtime"
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
class RuntimeBindingProposalCandidate:
    runtime_id: str
    binding_id: str
    adapter_name: str
    profile_digest: str
    artifact_digest: str
    admission_candidate_digest: str

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "binding_id": self.binding_id,
                "adapter_name": self.adapter_name,
                "profile_digest": self.profile_digest,
                "artifact_digest": self.artifact_digest,
                "admission_candidate_digest": self.admission_candidate_digest,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeBindingProposalResult:
    status: RuntimeBindingProposalStatus
    policy_digest: str
    admission_digest: str
    subject_repo_sha: str
    candidates: tuple[RuntimeBindingProposalCandidate, ...]
    blockers: tuple[str, ...]
    registry_mutation_executed: bool = False
    matrix_mutation_executed: bool = False
    activation_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.status is RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE
            and self.blockers
        ):
            raise NightShiftContractError(
                "ready runtime binding proposal cannot carry blockers"
            )
        if (
            self.registry_mutation_executed
            or self.matrix_mutation_executed
            or self.activation_executed
        ):
            raise NightShiftContractError(
                "runtime binding proposal cannot execute authority-changing mutations"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "admission_digest": self.admission_digest,
                "subject_repo_sha": self.subject_repo_sha,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "registry_mutation_executed": self.registry_mutation_executed,
                "matrix_mutation_executed": self.matrix_mutation_executed,
                "activation_executed": self.activation_executed,
            }
        )


@dataclass(frozen=True, slots=True)
class SignedRuntimeBindingProposal:
    proposal_digest: str
    trust_set_digest: str
    signer_identity: str
    attestation: SignedAttestation

    def __post_init__(self) -> None:
        proposal_digest = _digest(
            self.proposal_digest,
            field_name="proposal_digest",
        )
        trust_set_digest = _digest(
            self.trust_set_digest,
            field_name="trust_set_digest",
        )
        signer = self.signer_identity.strip()
        if not signer:
            raise NightShiftContractError("binding proposal signer identity is required")
        if self.attestation.key_id != signer:
            raise NightShiftContractError(
                "binding proposal attestation key does not match signer identity"
            )
        object.__setattr__(self, "proposal_digest", proposal_digest)
        object.__setattr__(self, "trust_set_digest", trust_set_digest)
        object.__setattr__(self, "signer_identity", signer)

    def digest(self) -> str:
        return content_digest(
            {
                "schema": BINDING_SIGNATURE_SCHEMA,
                "proposal_digest": self.proposal_digest,
                "trust_set_digest": self.trust_set_digest,
                "signer_identity": self.signer_identity,
                "attestation": {
                    **self.attestation.canonical_body(),
                    "signature_b64": self.attestation.signature_b64,
                },
            }
        )


def build_runtime_binding_proposal(
    *,
    admission: RuntimeAdapterAdmissionResult,
    profiles: tuple[RuntimeProfile, ...],
    subject_repo_sha: str,
    policy: RuntimeBindingProposalPolicy,
) -> RuntimeBindingProposalResult:
    repo_sha = _git_sha(subject_repo_sha, field_name="subject_repo_sha")
    if admission.subject_repo_sha != repo_sha:
        raise NightShiftContractError("binding proposal repository SHA mismatch")

    by_profile = {item.runtime_id: item for item in profiles}
    if len(by_profile) != len(profiles):
        raise NightShiftContractError("binding proposal profiles must be unique")
    if tuple(sorted(by_profile)) != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "binding proposal requires exactly candidate runtime profiles"
        )

    by_candidate = {item.runtime_id: item for item in admission.candidates}
    if len(by_candidate) != len(admission.candidates):
        raise NightShiftContractError(
            "binding proposal admission candidates must be unique"
        )

    blockers: set[str] = set()
    if (
        admission.status
        is not RuntimeAdapterAdmissionStatus.READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE
    ):
        blockers.add("ADAPTER_ADMISSION_NOT_READY")
    if admission.blockers:
        blockers.add("ADAPTER_ADMISSION_BLOCKED")

    candidates: list[RuntimeBindingProposalCandidate] = []
    for runtime_id in policy.candidate_runtime_ids:
        profile = by_profile[runtime_id]
        admitted = by_candidate.get(runtime_id)
        if admitted is None:
            blockers.add(f"{runtime_id.upper()}_ADMISSION_MISSING")
            continue
        if not admitted.ready_for_signed_adapter_binding_change:
            blockers.add(f"{runtime_id.upper()}_ADMISSION_NOT_READY")
            continue
        if admitted.artifact_digest is None:
            blockers.add(f"{runtime_id.upper()}_ARTIFACT_DIGEST_MISSING")
            continue
        if admitted.source_profile_digest != profile.digest():
            raise NightShiftContractError(
                "binding proposal profile digest does not match admission"
            )
        if profile.adapter.casefold().startswith("future_"):
            blockers.add(f"{runtime_id.upper()}_PLACEHOLDER_ADAPTER")
            continue
        candidates.append(
            RuntimeBindingProposalCandidate(
                runtime_id=runtime_id,
                binding_id=f"{runtime_id}:{profile.adapter}",
                adapter_name=profile.adapter,
                profile_digest=profile.digest(),
                artifact_digest=admitted.artifact_digest,
                admission_candidate_digest=admitted.digest(),
            )
        )

    ordered = tuple(candidates)
    if len(ordered) != len(policy.candidate_runtime_ids):
        blockers.add("BINDING_PROPOSAL_INCOMPLETE")
    ordered_blockers = tuple(sorted(blockers))
    return RuntimeBindingProposalResult(
        status=(
            RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE
            if not ordered_blockers
            else RuntimeBindingProposalStatus.BLOCKED
        ),
        policy_digest=policy.digest(),
        admission_digest=admission.digest(),
        subject_repo_sha=repo_sha,
        candidates=ordered,
        blockers=ordered_blockers,
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


def sign_runtime_binding_proposal(
    *,
    proposal: RuntimeBindingProposalResult,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    signer: AttestationSigner,
    issued_at: int,
    expires_at: int,
    nonce: str,
) -> SignedRuntimeBindingProposal:
    if (
        proposal.status is not RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE
        or proposal.blockers
    ):
        raise NightShiftContractError("cannot sign incomplete runtime binding proposal")
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError("binding proposal trust-set identity mismatch")
    if issued_at >= expires_at:
        raise NightShiftContractError(
            "cannot sign runtime binding proposal at or after expiry"
        )
    signer_identity = signer.key_id
    payload = _signature_payload(proposal, signer_identity=signer_identity)
    try:
        attestation = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected,
            signer=signer,
            purpose=AttestationPurpose.SECURITY_REVIEW,
            subject_digest=proposal.digest(),
            payload=payload,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return SignedRuntimeBindingProposal(
        proposal_digest=proposal.digest(),
        trust_set_digest=expected,
        signer_identity=signer_identity,
        attestation=attestation,
    )
