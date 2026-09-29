from dataclasses import replace

import pytest

from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_binding_proposal import (
    RuntimeBindingProposalCandidate,
    RuntimeBindingProposalResult,
    RuntimeBindingProposalStatus,
    sign_runtime_binding_proposal,
)
from core.night_shift.runtime_binding_verification import (
    ObservedRuntimeBinding,
    RuntimeBindingVerificationPolicy,
    RuntimeBindingVerificationStatus,
    verify_runtime_bindings,
)
from core.p3.contracts import content_digest

NOW = 10
VALID_UNTIL = 100


def _proposal() -> RuntimeBindingProposalResult:
    candidates = tuple(
        RuntimeBindingProposalCandidate(
            runtime_id=runtime_id,
            binding_id=f"{runtime_id}:{runtime_id}_adapter",
            adapter_name=f"{runtime_id}_adapter",
            profile_digest=content_digest({"profile": runtime_id}),
            artifact_digest=content_digest({"artifact": runtime_id}),
            admission_candidate_digest=content_digest({"admission": runtime_id}),
        )
        for runtime_id in ("dbos", "temporal")
    )
    return RuntimeBindingProposalResult(
        status=RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE,
        policy_digest=content_digest({"policy": "v2-19"}),
        admission_digest=content_digest({"admission": "v2-18"}),
        subject_repo_sha="a" * 40,
        candidates=candidates,
        blockers=(),
    )


def _trust_fixture() -> tuple[AttestationSigner, CryptoTrustSetV1]:
    signer = AttestationSigner.generate("runtime-binding-reviewer")
    trust_set = CryptoTrustSetV1(
        keys=(
            CryptoTrustKeyV1.from_public_key_bytes(
                key_id=signer.key_id,
                public_key=signer.public_key_bytes(),
                status=CryptoKeyStatus.ACTIVE,
                not_before=1,
                allowed_purposes=(AttestationPurpose.SECURITY_REVIEW,),
            ),
        )
    )
    return signer, trust_set


def _signed(proposal: RuntimeBindingProposalResult):
    signer, trust_set = _trust_fixture()
    signed = sign_runtime_binding_proposal(
        proposal=proposal,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        signer=signer,
        issued_at=NOW,
        expires_at=VALID_UNTIL,
        nonce="binding-proposal",
    )
    return signed, trust_set


def _observations(
    proposal: RuntimeBindingProposalResult,
) -> tuple[ObservedRuntimeBinding, ...]:
    registry = content_digest({"registry": "snapshot"})
    matrix = content_digest({"matrix": "snapshot"})
    return tuple(
        ObservedRuntimeBinding(
            runtime_id=item.runtime_id,
            binding_id=item.binding_id,
            proposal_candidate_digest=item.digest(),
            profile_digest=item.profile_digest,
            artifact_digest=item.artifact_digest,
            registry_snapshot_digest=registry,
            matrix_snapshot_digest=matrix,
            evidence_refs=(f"artifact:{item.runtime_id}:binding-observation",),
        )
        for item in proposal.candidates
    )


def test_v220_verifies_signed_exact_binding_without_activation() -> None:
    proposal = _proposal()
    signed, trust_set = _signed(proposal)
    result = verify_runtime_bindings(
        proposal=proposal,
        signed_proposal=signed,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        now_epoch=NOW + 1,
        observations=_observations(proposal),
        policy=RuntimeBindingVerificationPolicy(),
    )

    assert (
        result.status
        is RuntimeBindingVerificationStatus.READY_FOR_SHADOW_ACTIVATION_PLAN
    )
    assert result.signer_identity == signed.signer_identity
    assert result.signature_verification_digest
    assert not result.activation_executed


def test_v220_rejects_binding_identity_drift() -> None:
    proposal = _proposal()
    signed, trust_set = _signed(proposal)
    observations = _observations(proposal)
    poisoned = replace(observations[0], binding_id="dbos:other")

    with pytest.raises(
        NightShiftContractError,
        match="observed binding identity mismatch",
    ):
        verify_runtime_bindings(
            proposal=proposal,
            signed_proposal=signed,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now_epoch=NOW + 1,
            observations=(poisoned, observations[1]),
            policy=RuntimeBindingVerificationPolicy(),
        )


def test_v220_rejects_signed_proposal_digest_drift() -> None:
    proposal = _proposal()
    signed, trust_set = _signed(proposal)
    poisoned = replace(
        signed,
        proposal_digest=content_digest({"proposal": "other"}),
    )

    with pytest.raises(
        NightShiftContractError,
        match="signed binding proposal digest mismatch",
    ):
        verify_runtime_bindings(
            proposal=proposal,
            signed_proposal=poisoned,
            trust_set=trust_set,
            expected_trust_set_digest=trust_set.trust_set_digest,
            now_epoch=NOW + 1,
            observations=_observations(proposal),
            policy=RuntimeBindingVerificationPolicy(),
        )


def test_v220_requires_coherent_registry_snapshot() -> None:
    proposal = _proposal()
    signed, trust_set = _signed(proposal)
    observations = _observations(proposal)
    drifted = replace(
        observations[1],
        registry_snapshot_digest=content_digest({"registry": "other"}),
    )
    result = verify_runtime_bindings(
        proposal=proposal,
        signed_proposal=signed,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        now_epoch=NOW + 1,
        observations=(observations[0], drifted),
        policy=RuntimeBindingVerificationPolicy(),
    )

    assert result.status is RuntimeBindingVerificationStatus.BLOCKED
    assert "REGISTRY_SNAPSHOT_NOT_COHERENT" in result.blockers

def test_v220_ready_result_cannot_carry_blockers() -> None:
    proposal = _proposal()
    signed, trust_set = _signed(proposal)
    result = verify_runtime_bindings(
        proposal=proposal,
        signed_proposal=signed,
        trust_set=trust_set,
        expected_trust_set_digest=trust_set.trust_set_digest,
        now_epoch=NOW + 1,
        observations=_observations(proposal),
        policy=RuntimeBindingVerificationPolicy(),
    )

    with pytest.raises(
        NightShiftContractError,
        match="ready runtime binding verification cannot carry blockers",
    ):
        replace(result, blockers=("FORGED_BLOCKER",))
