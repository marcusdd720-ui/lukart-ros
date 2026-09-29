from dataclasses import replace

import pytest

from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_adapter_admission import (
    RuntimeAdapterAdmissionCandidate,
    RuntimeAdapterAdmissionResult,
    RuntimeAdapterAdmissionStatus,
)
from core.night_shift.runtime_binding_proposal import (
    RuntimeBindingProposalPolicy,
    RuntimeBindingProposalStatus,
    build_runtime_binding_proposal,
    sign_runtime_binding_proposal,
)
from core.night_shift.runtime_profiles import RuntimeEvidence, RuntimeProfile
from core.p3.contracts import content_digest

REPO_SHA = "a" * 40
NOW = 10
VALID_UNTIL = 100


def _profiles() -> tuple[RuntimeProfile, ...]:
    return (
        RuntimeProfile(
            runtime_id="dbos",
            adapter="dbos_adapter",
            evidence=RuntimeEvidence.VALIDATED,
            crash_resume=True,
            idempotent_steps=True,
            deterministic_replay=True,
            durable_timers=True,
            distributed_workers=True,
            requires_external_service=True,
            operational_rank=1,
            source_refs=("artifact:dbos-profile",),
        ),
        RuntimeProfile(
            runtime_id="temporal",
            adapter="temporal_adapter",
            evidence=RuntimeEvidence.VALIDATED,
            crash_resume=True,
            idempotent_steps=True,
            deterministic_replay=True,
            durable_timers=True,
            distributed_workers=True,
            requires_external_service=True,
            operational_rank=2,
            source_refs=("artifact:temporal-profile",),
        ),
    )


def _admission() -> RuntimeAdapterAdmissionResult:
    profiles = _profiles()
    candidates = tuple(
        RuntimeAdapterAdmissionCandidate(
            runtime_id=profile.runtime_id,
            source_profile_digest=profile.digest(),
            artifact_digest=content_digest({"artifact": profile.runtime_id}),
            conformance_run_digests=(
                content_digest({"run": profile.runtime_id, "index": 0}),
                content_digest({"run": profile.runtime_id, "index": 1}),
                content_digest({"run": profile.runtime_id, "index": 2}),
            ),
            ready_for_signed_adapter_binding_change=True,
            blockers=(),
        )
        for profile in profiles
    )
    return RuntimeAdapterAdmissionResult(
        status=RuntimeAdapterAdmissionStatus.READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE,
        policy_digest=content_digest({"policy": "v2-18"}),
        subject_repo_sha=REPO_SHA,
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


def test_v219_builds_advisory_binding_proposal_without_mutation() -> None:
    result = build_runtime_binding_proposal(
        admission=_admission(),
        profiles=_profiles(),
        subject_repo_sha=REPO_SHA,
        policy=RuntimeBindingProposalPolicy(),
    )

    assert result.status is RuntimeBindingProposalStatus.READY_FOR_HUMAN_SIGNATURE
    assert tuple(item.runtime_id for item in result.candidates) == ("dbos", "temporal")
    assert not result.registry_mutation_executed
    assert not result.matrix_mutation_executed
    assert not result.activation_executed


def test_v219_signs_exact_proposal_under_pinned_trust_set() -> None:
    proposal = build_runtime_binding_proposal(
        admission=_admission(),
        profiles=_profiles(),
        subject_repo_sha=REPO_SHA,
        policy=RuntimeBindingProposalPolicy(),
    )
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

    assert signed.proposal_digest == proposal.digest()
    assert signed.signer_identity == signer.key_id
    assert signed.trust_set_digest == trust_set.trust_set_digest


def test_v219_rejects_profile_digest_drift() -> None:
    admission = _admission()
    drifted = replace(
        admission.candidates[0],
        source_profile_digest=content_digest({"profile": "drift"}),
    )
    poisoned = replace(admission, candidates=(drifted, admission.candidates[1]))

    with pytest.raises(
        NightShiftContractError,
        match="profile digest does not match admission",
    ):
        build_runtime_binding_proposal(
            admission=poisoned,
            profiles=_profiles(),
            subject_repo_sha=REPO_SHA,
            policy=RuntimeBindingProposalPolicy(),
        )


def test_v219_policy_cannot_enable_automatic_activation() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="cannot mutate registry/matrix or activate",
    ):
        RuntimeBindingProposalPolicy(automatic_activation_enabled=True)

def test_v219_ready_result_cannot_carry_blockers() -> None:
    result = build_runtime_binding_proposal(
        admission=_admission(),
        profiles=_profiles(),
        subject_repo_sha=REPO_SHA,
        policy=RuntimeBindingProposalPolicy(),
    )

    with pytest.raises(
        NightShiftContractError,
        match="ready runtime binding proposal cannot carry blockers",
    ):
        replace(result, blockers=("FORGED_BLOCKER",))
