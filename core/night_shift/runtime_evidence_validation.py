"""Cryptographically reviewed runtime evidence validation boundary for Night Shift V2-17."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.crypto_agility_v1 import (
    CryptoAgilityV1Error,
    CryptoTrustSetV1,
    CryptoTrustVerifierV1,
    sign_attestation_v1,
)
from core.enterprise.contracts import (
    AttestationPurpose,
    AttestationSigner,
    SignedAttestation,
)
from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .runtime_evidence_acquisition import (
    RuntimeEvidenceAcquisitionResult,
    RuntimeEvidenceAcquisitionStatus,
)
from .runtime_profiles import RuntimeEvidence, RuntimeProfile

VALIDATION_REVIEW_SCHEMA = "night-shift-runtime-evidence-validation-review/v1"

class RuntimeEvidenceValidationStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_SIGNED_MATRIX_CHANGE = "READY_FOR_SIGNED_MATRIX_CHANGE"


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
class RuntimeEvidenceValidationPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_independent_reviews_per_runtime: int = 2
    automatic_matrix_mutation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-17 validation requires exactly DBOS and Temporal"
            )
        if self.min_independent_reviews_per_runtime < 2:
            raise NightShiftContractError(
                "runtime evidence validation requires at least two review identities"
            )
        if self.automatic_matrix_mutation_enabled:
            raise NightShiftContractError(
                "V2-17 cannot automatically mutate the runtime matrix"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_independent_reviews_per_runtime": (
                    self.min_independent_reviews_per_runtime
                ),
                "automatic_matrix_mutation_enabled": (
                    self.automatic_matrix_mutation_enabled
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceSignedReview:
    runtime_id: str
    acquisition_digest: str
    candidate_digest: str
    profile_digest: str
    subject_repo_sha: str
    trust_set_digest: str
    builder_identity: str
    reviewer_identity: str
    attestation: SignedAttestation

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        builder = self.builder_identity.strip()
        reviewer = self.reviewer_identity.strip()
        if not runtime_id or not builder or not reviewer:
            raise NightShiftContractError(
                "runtime validation review identity is required"
            )
        if builder == reviewer:
            raise NightShiftContractError(
                "builder cannot self-certify runtime validation review"
            )
        for field_name in (
            "acquisition_digest",
            "candidate_digest",
            "profile_digest",
            "trust_set_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "subject_repo_sha",
            _git_sha(self.subject_repo_sha, field_name="subject_repo_sha"),
        )
        if self.attestation.key_id != reviewer:
            raise NightShiftContractError(
                "runtime validation attestation key does not match reviewer identity"
            )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "builder_identity", builder)
        object.__setattr__(self, "reviewer_identity", reviewer)

    def digest(self) -> str:
        return content_digest(
            {
                "schema": VALIDATION_REVIEW_SCHEMA,
                "runtime_id": self.runtime_id,
                "acquisition_digest": self.acquisition_digest,
                "candidate_digest": self.candidate_digest,
                "profile_digest": self.profile_digest,
                "subject_repo_sha": self.subject_repo_sha,
                "trust_set_digest": self.trust_set_digest,
                "builder_identity": self.builder_identity,
                "reviewer_identity": self.reviewer_identity,
                "attestation_digest": self.attestation.digest(),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceValidationCandidate:
    runtime_id: str
    source_profile_digest: str
    target_evidence: RuntimeEvidence
    verified_review_digests: tuple[str, ...]
    ready_for_signed_matrix_change: bool
    blockers: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "source_profile_digest": self.source_profile_digest,
                "target_evidence": self.target_evidence.value,
                "verified_review_digests": list(self.verified_review_digests),
                "ready_for_signed_matrix_change": (
                    self.ready_for_signed_matrix_change
                ),
                "blockers": list(self.blockers),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceValidationResult:
    status: RuntimeEvidenceValidationStatus
    policy_digest: str
    acquisition_digest: str
    subject_repo_sha: str
    trust_set_digest: str
    builder_identity: str
    candidates: tuple[RuntimeEvidenceValidationCandidate, ...]
    blockers: tuple[str, ...]
    automatic_matrix_mutation_executed: bool = False
    def __post_init__(self) -> None:
        if self.automatic_matrix_mutation_executed:
            raise NightShiftContractError(
                "runtime validation cannot mutate the matrix automatically"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "acquisition_digest": self.acquisition_digest,
                "subject_repo_sha": self.subject_repo_sha,
                "trust_set_digest": self.trust_set_digest,
                "builder_identity": self.builder_identity,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "automatic_matrix_mutation_executed": (
                    self.automatic_matrix_mutation_executed
                ),
            }
        )


def _candidate_for_runtime(
    acquisition: RuntimeEvidenceAcquisitionResult,
    runtime_id: str,
):
    return next(
        (item for item in acquisition.candidates if item.runtime_id == runtime_id),
        None,
    )
def _review_payload(
    *,
    acquisition: RuntimeEvidenceAcquisitionResult,
    candidate_digest: str,
    profile: RuntimeProfile,
    builder_identity: str,
    reviewer_identity: str,
    subject_repo_sha: str,
) -> dict[str, object]:
    return {
        "schema": VALIDATION_REVIEW_SCHEMA,
        "artifact": "runtime_evidence_validation_review",
        "runtime_id": profile.runtime_id,
        "acquisition_digest": acquisition.digest(),
        "candidate_digest": candidate_digest,
        "profile_digest": profile.digest(),
        "source_evidence": RuntimeEvidence.DOCUMENTED.value,
        "target_evidence": RuntimeEvidence.VALIDATED.value,
        "subject_repo_sha": subject_repo_sha,
        "builder_identity": builder_identity,
        "reviewer_identity": reviewer_identity,
    }


def sign_runtime_evidence_review(
    *,
    acquisition: RuntimeEvidenceAcquisitionResult,
    profile: RuntimeProfile,
    subject_repo_sha: str,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    reviewer_signer: AttestationSigner,
    builder_identity: str,
    issued_at: int,
    expires_at: int,
    nonce: str,
) -> RuntimeEvidenceSignedReview:
    if (
        acquisition.status
        is not RuntimeEvidenceAcquisitionStatus.READY_FOR_HUMAN_VALIDATION
        or acquisition.blockers
    ):
        raise NightShiftContractError(
            "cannot sign validation review for incomplete acquisition"
        )
    candidate = _candidate_for_runtime(acquisition, profile.runtime_id)
    if candidate is None or not candidate.evidence_complete:
        raise NightShiftContractError(
            "cannot sign validation review for incomplete candidate"
        )
    if profile.evidence is not RuntimeEvidence.DOCUMENTED:
        raise NightShiftContractError(
            "runtime validation review requires DOCUMENTED source profile"
        )
    if candidate.profile_digest != profile.digest():
        raise NightShiftContractError(
            "runtime validation review profile digest mismatch"
        )
    repo_sha = _git_sha(subject_repo_sha, field_name="subject_repo_sha")
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError(
            "runtime validation trust-set identity mismatch"
        )
    if issued_at >= expires_at:
        raise NightShiftContractError(
            "cannot sign runtime validation review at or after expiry"
        )
    builder = builder_identity.strip()
    reviewer_identity = reviewer_signer.key_id
    if not builder:
        raise NightShiftContractError(
            "runtime validation builder identity is required"
        )
    if builder == reviewer_identity:
        raise NightShiftContractError(
            "builder cannot self-certify runtime validation review"
        )
    payload = _review_payload(
        acquisition=acquisition,
        candidate_digest=candidate.digest(),
        profile=profile,
        builder_identity=builder,
        reviewer_identity=reviewer_identity,
        subject_repo_sha=repo_sha,
    )
    try:
        attestation = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected,
            signer=reviewer_signer,
            purpose=AttestationPurpose.SECURITY_REVIEW,
            subject_digest=acquisition.digest(),
            payload=payload,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return RuntimeEvidenceSignedReview(
        runtime_id=profile.runtime_id,
        acquisition_digest=acquisition.digest(),
        candidate_digest=candidate.digest(),
        profile_digest=profile.digest(),
        subject_repo_sha=repo_sha,
        trust_set_digest=expected,
        builder_identity=builder,
        reviewer_identity=reviewer_identity,
        attestation=attestation,
    )


def _blocked_candidate(
    profile: RuntimeProfile,
    *blockers: str,
) -> RuntimeEvidenceValidationCandidate:
    ordered = tuple(sorted(set(blockers)))
    return RuntimeEvidenceValidationCandidate(
        runtime_id=profile.runtime_id,
        source_profile_digest=profile.digest(),
        target_evidence=RuntimeEvidence.VALIDATED,
        verified_review_digests=(),
        ready_for_signed_matrix_change=False,
        blockers=ordered,
    )


def evaluate_runtime_evidence_validation(
    *,
    acquisition: RuntimeEvidenceAcquisitionResult,
    profiles: tuple[RuntimeProfile, ...],
    reviews: tuple[RuntimeEvidenceSignedReview, ...],
    subject_repo_sha: str,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    builder_identity: str,
    now_epoch: int,
    policy: RuntimeEvidenceValidationPolicy,
) -> RuntimeEvidenceValidationResult:
    repo_sha = _git_sha(subject_repo_sha, field_name="subject_repo_sha")
    builder = builder_identity.strip()
    if not builder:
        raise NightShiftContractError(
            "runtime validation builder identity is required"
        )
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError(
            "runtime validation trust-set identity mismatch"
        )
    by_id = {profile.runtime_id: profile for profile in profiles}
    if len(by_id) != len(profiles):
        raise NightShiftContractError(
            "runtime validation profiles must be unique"
        )
    if tuple(sorted(by_id)) != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "runtime validation requires exactly the candidate profiles"
        )
    acquisition_ids = tuple(
        sorted(item.runtime_id for item in acquisition.candidates)
    )
    if acquisition_ids != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "runtime validation acquisition candidate set mismatch"
        )
    unknown_reviews = [
        review.runtime_id
        for review in reviews
        if review.runtime_id not in policy.candidate_runtime_ids
    ]
    if unknown_reviews:
        raise NightShiftContractError(
            "runtime validation review references unknown runtime"
        )
    if (
        acquisition.status
        is not RuntimeEvidenceAcquisitionStatus.READY_FOR_HUMAN_VALIDATION
        or acquisition.blockers
    ):
        if reviews:
            raise NightShiftContractError(
                "blocked acquisition cannot carry validation reviews"
            )
        candidates = tuple(
            _blocked_candidate(by_id[item], "ACQUISITION_NOT_READY")
            for item in policy.candidate_runtime_ids
        )
        return RuntimeEvidenceValidationResult(
            status=RuntimeEvidenceValidationStatus.BLOCKED,
            policy_digest=policy.digest(),
            acquisition_digest=acquisition.digest(),
            subject_repo_sha=repo_sha,
            trust_set_digest=expected,
            builder_identity=builder,
            candidates=candidates,
            blockers=("RUNTIME_VALIDATION_INCOMPLETE",),
        )

    verifier = CryptoTrustVerifierV1(
        trust_set,
        expected_trust_set_digest=expected,
    )
    results: list[RuntimeEvidenceValidationCandidate] = []
    for runtime_id in policy.candidate_runtime_ids:
        profile = by_id[runtime_id]
        candidate = _candidate_for_runtime(acquisition, runtime_id)
        if candidate is None:
            raise NightShiftContractError(
                "runtime validation candidate is missing"
            )
        if candidate.profile_digest != profile.digest():
            raise NightShiftContractError(
                "runtime validation candidate profile digest mismatch"
            )

        blockers: set[str] = set()
        if profile.evidence is not RuntimeEvidence.DOCUMENTED:
            blockers.add("SOURCE_PROFILE_NOT_DOCUMENTED")
        if not candidate.evidence_complete:
            blockers.add("ACQUISITION_CANDIDATE_INCOMPLETE")

        bound_reviews = tuple(
            review for review in reviews if review.runtime_id == runtime_id
        )
        identities = [review.reviewer_identity for review in bound_reviews]
        if len(set(identities)) != len(identities):
            raise NightShiftContractError(
                "runtime validation reviewer identities must be unique per runtime"
            )

        verified_digests: list[str] = []
        for review in bound_reviews:
            if review.builder_identity != builder:
                raise NightShiftContractError(
                    "runtime validation review builder identity mismatch"
                )
            if review.reviewer_identity == builder:
                raise NightShiftContractError(
                    "builder cannot self-certify runtime validation review"
                )
            if review.acquisition_digest != acquisition.digest():
                raise NightShiftContractError(
                    "runtime validation review acquisition digest mismatch"
                )
            if review.candidate_digest != candidate.digest():
                raise NightShiftContractError(
                    "runtime validation review candidate digest mismatch"
                )
            if review.profile_digest != profile.digest():
                raise NightShiftContractError(
                    "runtime validation review profile digest mismatch"
                )
            if review.subject_repo_sha != repo_sha:
                raise NightShiftContractError(
                    "runtime validation review repository SHA mismatch"
                )
            if review.trust_set_digest != expected:
                raise NightShiftContractError(
                    "runtime validation review trust-set mismatch"
                )
            payload = _review_payload(
                acquisition=acquisition,
                candidate_digest=candidate.digest(),
                profile=profile,
                builder_identity=builder,
                reviewer_identity=review.reviewer_identity,
                subject_repo_sha=repo_sha,
            )
            try:
                verification = verifier.verify(
                    review.attestation,
                    expected_purpose=AttestationPurpose.SECURITY_REVIEW,
                    expected_subject_digest=acquisition.digest(),
                    payload=payload,
                    now=now_epoch,
                )
            except CryptoAgilityV1Error as exc:
                raise NightShiftContractError(str(exc)) from exc
            verified_digests.append(verification.verification_digest)

        if (
            len(verified_digests)
            < policy.min_independent_reviews_per_runtime
        ):
            blockers.add("INSUFFICIENT_CRYPTOGRAPHIC_REVIEWS")
        ordered_blockers = tuple(sorted(blockers))
        results.append(
            RuntimeEvidenceValidationCandidate(
                runtime_id=runtime_id,
                source_profile_digest=profile.digest(),
                target_evidence=RuntimeEvidence.VALIDATED,
                verified_review_digests=tuple(sorted(verified_digests)),
                ready_for_signed_matrix_change=not ordered_blockers,
                blockers=ordered_blockers,
            )
        )

    candidates = tuple(results)
    result_blockers: tuple[str, ...] = ()
    if not all(item.ready_for_signed_matrix_change for item in candidates):
        result_blockers = ("RUNTIME_VALIDATION_INCOMPLETE",)
    status = (
        RuntimeEvidenceValidationStatus.READY_FOR_SIGNED_MATRIX_CHANGE
        if not result_blockers
        else RuntimeEvidenceValidationStatus.BLOCKED
    )
    return RuntimeEvidenceValidationResult(
        status=status,
        policy_digest=policy.digest(),
        acquisition_digest=acquisition.digest(),
        subject_repo_sha=repo_sha,
        trust_set_digest=expected,
        builder_identity=builder,
        candidates=candidates,
        blockers=result_blockers,
    )
