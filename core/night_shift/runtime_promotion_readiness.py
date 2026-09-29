"""Cryptographic human-gated runtime promotion readiness for Night Shift V2-23."""

from __future__ import annotations

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
from .runtime_shadow_activation_evidence import (
    RuntimeShadowEvidenceResult,
    RuntimeShadowEvidenceStatus,
)

PROMOTION_REVIEW_SCHEMA = "night-shift-runtime-promotion-review/v1"


class RuntimePromotionReadinessStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN_PROMOTION_DECISION = "READY_FOR_HUMAN_PROMOTION_DECISION"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class RuntimePromotionReview:
    runtime_id: str
    shadow_evidence_digest: str
    shadow_candidate_digest: str
    trust_set_digest: str
    builder_identity: str
    reviewer_identity: str
    approved: bool
    attestation: SignedAttestation

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        builder = self.builder_identity.strip()
        reviewer = self.reviewer_identity.strip()
        if not runtime_id or not builder or not reviewer:
            raise NightShiftContractError("promotion review identity is required")
        if builder == reviewer:
            raise NightShiftContractError(
                "builder cannot self-approve runtime promotion review"
            )
        if type(self.approved) is not bool:
            raise NightShiftContractError("promotion review approval must be boolean")
        if self.attestation.key_id != reviewer:
            raise NightShiftContractError(
                "promotion review attestation key does not match reviewer identity"
            )
        object.__setattr__(
            self,
            "shadow_evidence_digest",
            _digest(self.shadow_evidence_digest, field_name="shadow_evidence_digest"),
        )
        object.__setattr__(
            self,
            "shadow_candidate_digest",
            _digest(self.shadow_candidate_digest, field_name="shadow_candidate_digest"),
        )
        object.__setattr__(
            self,
            "trust_set_digest",
            _digest(self.trust_set_digest, field_name="trust_set_digest"),
        )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "builder_identity", builder)
        object.__setattr__(self, "reviewer_identity", reviewer)

    def digest(self) -> str:
        return content_digest(
            {
                "schema": PROMOTION_REVIEW_SCHEMA,
                "runtime_id": self.runtime_id,
                "shadow_evidence_digest": self.shadow_evidence_digest,
                "shadow_candidate_digest": self.shadow_candidate_digest,
                "trust_set_digest": self.trust_set_digest,
                "builder_identity": self.builder_identity,
                "reviewer_identity": self.reviewer_identity,
                "approved": self.approved,
                "attestation": {
                    **self.attestation.canonical_body(),
                    "signature_b64": self.attestation.signature_b64,
                },
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimePromotionReadinessPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_distinct_reviewers_per_runtime: int = 2
    automatic_promotion_enabled: bool = False
    production_publication_enabled: bool = False
    registry_mutation_enabled: bool = False
    matrix_mutation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-23 promotion readiness requires exactly DBOS and Temporal"
            )
        if self.min_distinct_reviewers_per_runtime < 2:
            raise NightShiftContractError(
                "V2-23 requires at least two distinct reviewers per runtime"
            )
        if (
            self.automatic_promotion_enabled
            or self.production_publication_enabled
            or self.registry_mutation_enabled
            or self.matrix_mutation_enabled
        ):
            raise NightShiftContractError(
                "V2-23 cannot auto-promote, publish, or mutate runtime authority"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_distinct_reviewers_per_runtime": (
                    self.min_distinct_reviewers_per_runtime
                ),
                "automatic_promotion_enabled": self.automatic_promotion_enabled,
                "production_publication_enabled": self.production_publication_enabled,
                "registry_mutation_enabled": self.registry_mutation_enabled,
                "matrix_mutation_enabled": self.matrix_mutation_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimePromotionReadinessCandidate:
    runtime_id: str
    shadow_candidate_digest: str
    verified_review_digests: tuple[str, ...]
    reviewer_identities: tuple[str, ...]
    ready_for_human_promotion_decision: bool
    blockers: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "shadow_candidate_digest": self.shadow_candidate_digest,
                "verified_review_digests": list(self.verified_review_digests),
                "reviewer_identities": list(self.reviewer_identities),
                "ready_for_human_promotion_decision": (
                    self.ready_for_human_promotion_decision
                ),
                "blockers": list(self.blockers),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimePromotionReadinessResult:
    status: RuntimePromotionReadinessStatus
    policy_digest: str
    shadow_evidence_digest: str
    trust_set_digest: str
    builder_identity: str
    candidates: tuple[RuntimePromotionReadinessCandidate, ...]
    blockers: tuple[str, ...]
    promotion_executed: bool = False
    production_publication_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.status
            is RuntimePromotionReadinessStatus.READY_FOR_HUMAN_PROMOTION_DECISION
            and self.blockers
        ):
            raise NightShiftContractError(
                "ready runtime promotion result cannot carry blockers"
            )
        if self.promotion_executed or self.production_publication_executed:
            raise NightShiftContractError(
                "promotion readiness cannot promote or publish"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "shadow_evidence_digest": self.shadow_evidence_digest,
                "trust_set_digest": self.trust_set_digest,
                "builder_identity": self.builder_identity,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "promotion_executed": self.promotion_executed,
                "production_publication_executed": self.production_publication_executed,
            }
        )


def _candidate_for_runtime(
    shadow_evidence: RuntimeShadowEvidenceResult,
    runtime_id: str,
):
    return next(
        (
            item
            for item in shadow_evidence.candidates
            if item.runtime_id == runtime_id
        ),
        None,
    )


def _review_payload(
    *,
    shadow_evidence: RuntimeShadowEvidenceResult,
    runtime_id: str,
    shadow_candidate_digest: str,
    builder_identity: str,
    reviewer_identity: str,
    approved: bool,
) -> dict[str, object]:
    return {
        "schema": PROMOTION_REVIEW_SCHEMA,
        "artifact": "runtime_promotion_review",
        "runtime_id": runtime_id,
        "shadow_evidence_digest": shadow_evidence.digest(),
        "shadow_candidate_digest": shadow_candidate_digest,
        "builder_identity": builder_identity,
        "reviewer_identity": reviewer_identity,
        "approved": approved,
    }


def sign_runtime_promotion_review(
    *,
    shadow_evidence: RuntimeShadowEvidenceResult,
    runtime_id: str,
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    builder_identity: str,
    reviewer_signer: AttestationSigner,
    approved: bool,
    issued_at: int,
    expires_at: int,
    nonce: str,
) -> RuntimePromotionReview:
    if (
        shadow_evidence.status
        is not RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW
        or shadow_evidence.blockers
    ):
        raise NightShiftContractError(
            "cannot sign promotion review for incomplete shadow evidence"
        )
    candidate = _candidate_for_runtime(shadow_evidence, runtime_id)
    if candidate is None or not candidate.ready_for_promotion_review:
        raise NightShiftContractError(
            "cannot sign promotion review for incomplete runtime candidate"
        )
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError("promotion review trust-set identity mismatch")
    builder = builder_identity.strip()
    reviewer = reviewer_signer.key_id
    if not builder:
        raise NightShiftContractError("promotion review builder identity is required")
    if builder == reviewer:
        raise NightShiftContractError(
            "builder cannot self-approve runtime promotion review"
        )
    if type(approved) is not bool:
        raise NightShiftContractError("promotion review approval must be boolean")
    if issued_at >= expires_at:
        raise NightShiftContractError(
            "cannot sign runtime promotion review at or after expiry"
        )
    payload = _review_payload(
        shadow_evidence=shadow_evidence,
        runtime_id=runtime_id,
        shadow_candidate_digest=candidate.digest(),
        builder_identity=builder,
        reviewer_identity=reviewer,
        approved=approved,
    )
    try:
        attestation = sign_attestation_v1(
            trust_set=trust_set,
            expected_trust_set_digest=expected,
            signer=reviewer_signer,
            purpose=AttestationPurpose.SECURITY_REVIEW,
            subject_digest=shadow_evidence.digest(),
            payload=payload,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
    except CryptoAgilityV1Error as exc:
        raise NightShiftContractError(str(exc)) from exc
    return RuntimePromotionReview(
        runtime_id=runtime_id,
        shadow_evidence_digest=shadow_evidence.digest(),
        shadow_candidate_digest=candidate.digest(),
        trust_set_digest=expected,
        builder_identity=builder,
        reviewer_identity=reviewer,
        approved=approved,
        attestation=attestation,
    )


def evaluate_runtime_promotion_readiness(
    *,
    shadow_evidence: RuntimeShadowEvidenceResult,
    reviews: tuple[RuntimePromotionReview, ...],
    trust_set: CryptoTrustSetV1,
    expected_trust_set_digest: str,
    builder_identity: str,
    now_epoch: int,
    policy: RuntimePromotionReadinessPolicy,
) -> RuntimePromotionReadinessResult:
    expected = _digest(
        expected_trust_set_digest,
        field_name="expected_trust_set_digest",
    )
    if trust_set.trust_set_digest != expected:
        raise NightShiftContractError("promotion readiness trust-set identity mismatch")
    builder = builder_identity.strip()
    if not builder:
        raise NightShiftContractError("promotion readiness builder identity is required")

    if shadow_evidence.status is not RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW:
        if reviews:
            raise NightShiftContractError(
                "blocked shadow evidence cannot carry promotion reviews"
            )
        return RuntimePromotionReadinessResult(
            status=RuntimePromotionReadinessStatus.BLOCKED,
            policy_digest=policy.digest(),
            shadow_evidence_digest=shadow_evidence.digest(),
            trust_set_digest=expected,
            builder_identity=builder,
            candidates=(),
            blockers=("SHADOW_EVIDENCE_NOT_READY",),
        )

    shadow_by_runtime = {item.runtime_id: item for item in shadow_evidence.candidates}
    if len(shadow_by_runtime) != len(shadow_evidence.candidates):
        raise NightShiftContractError("shadow evidence candidates must be unique")
    if tuple(sorted(shadow_by_runtime)) != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "promotion readiness requires exactly candidate runtimes"
        )

    unknown = set(item.runtime_id for item in reviews) - set(policy.candidate_runtime_ids)
    if unknown:
        raise NightShiftContractError("promotion review references unknown runtime")
    verifier = CryptoTrustVerifierV1(
        trust_set,
        expected_trust_set_digest=expected,
    )

    candidates: list[RuntimePromotionReadinessCandidate] = []
    for runtime_id in policy.candidate_runtime_ids:
        shadow = shadow_by_runtime[runtime_id]
        bound = tuple(item for item in reviews if item.runtime_id == runtime_id)
        blockers: set[str] = set()
        verified_digests: list[str] = []

        for item in bound:
            if item.trust_set_digest != expected:
                raise NightShiftContractError(
                    "promotion review trust-set digest mismatch"
                )
            if item.builder_identity != builder:
                raise NightShiftContractError(
                    "promotion review builder identity mismatch"
                )
            if item.reviewer_identity == builder:
                raise NightShiftContractError(
                    "builder cannot self-approve runtime promotion review"
                )
            if item.shadow_evidence_digest != shadow_evidence.digest():
                raise NightShiftContractError(
                    "promotion review shadow evidence digest mismatch"
                )
            if item.shadow_candidate_digest != shadow.digest():
                raise NightShiftContractError(
                    "promotion review shadow candidate digest mismatch"
                )
            payload = _review_payload(
                shadow_evidence=shadow_evidence,
                runtime_id=runtime_id,
                shadow_candidate_digest=shadow.digest(),
                builder_identity=builder,
                reviewer_identity=item.reviewer_identity,
                approved=item.approved,
            )
            try:
                verified = verifier.verify(
                    item.attestation,
                    expected_purpose=AttestationPurpose.SECURITY_REVIEW,
                    expected_subject_digest=shadow_evidence.digest(),
                    payload=payload,
                    now=now_epoch,
                )
            except CryptoAgilityV1Error as exc:
                raise NightShiftContractError(str(exc)) from exc
            verified_digests.append(verified.verification_digest)

        reviewers = tuple(sorted({item.reviewer_identity for item in bound}))
        if len(reviewers) < policy.min_distinct_reviewers_per_runtime:
            blockers.add("INSUFFICIENT_DISTINCT_REVIEWERS")
        if any(not item.approved for item in bound):
            blockers.add("PROMOTION_REVIEW_REJECTED")

        ordered_blockers = tuple(sorted(blockers))
        candidates.append(
            RuntimePromotionReadinessCandidate(
                runtime_id=runtime_id,
                shadow_candidate_digest=shadow.digest(),
                verified_review_digests=tuple(sorted(verified_digests)),
                reviewer_identities=reviewers,
                ready_for_human_promotion_decision=not ordered_blockers,
                blockers=ordered_blockers,
            )
        )

    ordered = tuple(candidates)
    result_blockers: tuple[str, ...] = ()
    if not all(item.ready_for_human_promotion_decision for item in ordered):
        result_blockers = ("PROMOTION_READINESS_INCOMPLETE",)
    return RuntimePromotionReadinessResult(
        status=(
            RuntimePromotionReadinessStatus.READY_FOR_HUMAN_PROMOTION_DECISION
            if not result_blockers
            else RuntimePromotionReadinessStatus.BLOCKED
        ),
        policy_digest=policy.digest(),
        shadow_evidence_digest=shadow_evidence.digest(),
        trust_set_digest=expected,
        builder_identity=builder,
        candidates=ordered,
        blockers=result_blockers,
    )
