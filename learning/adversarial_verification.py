"""Evidence-first adversarial verification for controlled multi-agent reasoning.

P7 treats adversarial agents as independent critics, not voters. No number of
supportive agents may override rejected provenance, unsupported claims, or an
unresolved blocking challenge.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from core.models.ids import AgentId

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _required_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be blank")
    return normalized


def _require_sha256(name: str, value: str) -> str:
    normalized = _required_text(name, value).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a 64-character SHA-256 digest")
    return normalized


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_digests(
    name: str,
    values: tuple[str, ...],
    *,
    required: bool,
) -> tuple[str, ...]:
    normalized = tuple(_require_sha256(name, value) for value in values)
    if required and not normalized:
        raise ValueError(f"{name} requires at least one digest")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} digests must be unique")
    return normalized


class EvidenceVerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ReviewStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ChallengeResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UPHELD = "upheld"
    INCONCLUSIVE = "inconclusive"


class AdversarialVerificationStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class VerificationProposal:
    """Digest-bound subject proposed for independent verification."""

    proposal_id: str
    generator_agent_id: AgentId
    subject_type: str
    subject_digest: str
    claim_digests: tuple[str, ...]
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposal_id",
            _required_text("proposal_id", self.proposal_id),
        )
        object.__setattr__(
            self,
            "subject_type",
            _required_text("subject_type", self.subject_type),
        )
        object.__setattr__(
            self,
            "subject_digest",
            _require_sha256("subject_digest", self.subject_digest),
        )
        object.__setattr__(
            self,
            "claim_digests",
            _normalized_digests("claim", self.claim_digests, required=True),
        )
        object.__setattr__(
            self,
            "evidence_digests",
            _normalized_digests("evidence", self.evidence_digests, required=True),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "claim_digests": list(self.claim_digests),
            "evidence_digests": list(self.evidence_digests),
            "generator_agent_id": str(self.generator_agent_id),
            "proposal_id": self.proposal_id,
            "subject_digest": self.subject_digest,
            "subject_type": self.subject_type,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True, order=True)
class ChallengeFinding:
    code: str
    claim_digest: str
    rationale: str
    blocking: bool
    evidence_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text("challenge code", self.code))
        object.__setattr__(
            self,
            "claim_digest",
            _require_sha256("claim_digest", self.claim_digest),
        )
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))
        object.__setattr__(
            self,
            "evidence_digests",
            _normalized_digests(
                "challenge evidence",
                self.evidence_digests,
                required=False,
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "blocking": self.blocking,
            "claim_digest": self.claim_digest,
            "code": self.code,
            "evidence_digests": list(self.evidence_digests),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ChallengeAssessment:
    challenger_agent_id: AgentId
    proposal_digest: str
    findings: tuple[ChallengeFinding, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposal_digest",
            _require_sha256("proposal_digest", self.proposal_digest),
        )
        codes = [finding.code for finding in self.findings]
        if len(codes) != len(set(codes)):
            raise ValueError("challenge finding codes must be unique within one assessment")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "challenger_agent_id": str(self.challenger_agent_id),
            "findings": [finding.canonical_dict() for finding in sorted(self.findings)],
            "proposal_digest": self.proposal_digest,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True, order=True)
class ChallengeResolution:
    challenge_code: str
    status: ChallengeResolutionStatus
    evidence_digests: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "challenge_code",
            _required_text("challenge_code", self.challenge_code),
        )
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))
        object.__setattr__(
            self,
            "evidence_digests",
            _normalized_digests(
                "resolution evidence",
                self.evidence_digests,
                required=True,
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "challenge_code": self.challenge_code,
            "evidence_digests": list(self.evidence_digests),
            "rationale": self.rationale,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class EvidenceVerification:
    """Independent evidence verdict with asymmetric veto power."""

    verifier_agent_id: AgentId
    proposal_digest: str
    status: EvidenceVerificationStatus
    checked_evidence_digests: tuple[str, ...]
    rejected_evidence_digests: tuple[str, ...] = ()
    unsupported_claim_digests: tuple[str, ...] = ()
    challenge_resolutions: tuple[ChallengeResolution, ...] = ()
    rationale: str = "evidence verification completed"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposal_digest",
            _require_sha256("proposal_digest", self.proposal_digest),
        )
        checked = _normalized_digests(
            "checked evidence",
            self.checked_evidence_digests,
            required=True,
        )
        rejected = _normalized_digests(
            "rejected evidence",
            self.rejected_evidence_digests,
            required=False,
        )
        unsupported = _normalized_digests(
            "unsupported claim",
            self.unsupported_claim_digests,
            required=False,
        )
        if not set(rejected).issubset(set(checked)):
            raise ValueError("rejected evidence must be a subset of checked evidence")
        codes = [resolution.challenge_code for resolution in self.challenge_resolutions]
        if len(codes) != len(set(codes)):
            raise ValueError("challenge resolutions must be unique by challenge code")
        object.__setattr__(self, "checked_evidence_digests", checked)
        object.__setattr__(self, "rejected_evidence_digests", rejected)
        object.__setattr__(self, "unsupported_claim_digests", unsupported)
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "challenge_resolutions": [
                resolution.canonical_dict()
                for resolution in sorted(self.challenge_resolutions)
            ],
            "checked_evidence_digests": list(self.checked_evidence_digests),
            "proposal_digest": self.proposal_digest,
            "rationale": self.rationale,
            "rejected_evidence_digests": list(self.rejected_evidence_digests),
            "status": self.status.value,
            "unsupported_claim_digests": list(self.unsupported_claim_digests),
            "verifier_agent_id": str(self.verifier_agent_id),
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ReviewAssessment:
    """Independent process review; it cannot substitute for evidence."""

    reviewer_agent_id: AgentId
    proposal_digest: str
    status: ReviewStatus
    issues: tuple[str, ...] = ()
    rationale: str = "independent review completed"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposal_digest",
            _require_sha256("proposal_digest", self.proposal_digest),
        )
        issues = tuple(item.strip() for item in self.issues)
        if issues and not all(issues):
            raise ValueError("review issues cannot be blank")
        if len(issues) != len(set(issues)):
            raise ValueError("review issues must be unique")
        object.__setattr__(self, "issues", issues)
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "issues": list(self.issues),
            "proposal_digest": self.proposal_digest,
            "rationale": self.rationale,
            "reviewer_agent_id": str(self.reviewer_agent_id),
            "status": self.status.value,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class AdversarialVerificationDecision:
    """Decision artifact only; never mutation or deployment authority."""

    status: AdversarialVerificationStatus
    reason: str
    proposal_digest: str
    proposal_subject_type: str
    proposal_subject_digest: str
    challenge_digests: tuple[str, ...]
    evidence_verification_digest: str
    review_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _required_text("reason", self.reason))
        object.__setattr__(
            self,
            "proposal_digest",
            _require_sha256("proposal_digest", self.proposal_digest),
        )
        object.__setattr__(
            self,
            "proposal_subject_type",
            _required_text("proposal_subject_type", self.proposal_subject_type),
        )
        object.__setattr__(
            self,
            "proposal_subject_digest",
            _require_sha256("proposal_subject_digest", self.proposal_subject_digest),
        )
        object.__setattr__(
            self,
            "challenge_digests",
            _normalized_digests("challenge", self.challenge_digests, required=True),
        )
        object.__setattr__(
            self,
            "evidence_verification_digest",
            _require_sha256(
                "evidence_verification_digest",
                self.evidence_verification_digest,
            ),
        )
        object.__setattr__(
            self,
            "review_digest",
            _require_sha256("review_digest", self.review_digest),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "challenge_digests": list(self.challenge_digests),
            "evidence_verification_digest": self.evidence_verification_digest,
            "proposal_digest": self.proposal_digest,
            "proposal_subject_digest": self.proposal_subject_digest,
            "proposal_subject_type": self.proposal_subject_type,
            "reason": self.reason,
            "review_digest": self.review_digest,
            "status": self.status.value,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


class AdversarialVerificationGate:
    """Resolve by evidence and independence, never by majority vote."""

    def evaluate(
        self,
        proposal: VerificationProposal,
        challenges: tuple[ChallengeAssessment, ...],
        evidence: EvidenceVerification,
        review: ReviewAssessment,
    ) -> AdversarialVerificationDecision:
        if not challenges:
            raise ValueError("adversarial verification requires at least one challenger")

        proposal_digest = proposal.digest()
        challenge_digests = tuple(sorted(challenge.digest() for challenge in challenges))

        def decide(
            status: AdversarialVerificationStatus,
            reason: str,
        ) -> AdversarialVerificationDecision:
            return AdversarialVerificationDecision(
                status=status,
                reason=reason,
                proposal_digest=proposal_digest,
                proposal_subject_type=proposal.subject_type,
                proposal_subject_digest=proposal.subject_digest,
                challenge_digests=challenge_digests,
                evidence_verification_digest=evidence.digest(),
                review_digest=review.digest(),
            )

        challenger_ids = [str(challenge.challenger_agent_id) for challenge in challenges]
        if len(challenger_ids) != len(set(challenger_ids)):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "challenger identities must be independent and unique",
            )
        role_ids = {
            str(proposal.generator_agent_id),
            *challenger_ids,
            str(evidence.verifier_agent_id),
            str(review.reviewer_agent_id),
        }
        if len(role_ids) != len(challenger_ids) + 3:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                (
                    "generator, challengers, evidence verifier, and reviewer "
                    "must be independent"
                ),
            )

        if any(challenge.proposal_digest != proposal_digest for challenge in challenges):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "challenger artifact is not bound to the exact proposal",
            )
        if evidence.proposal_digest != proposal_digest:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "evidence verification is not bound to the exact proposal",
            )
        if review.proposal_digest != proposal_digest:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "review is not bound to the exact proposal",
            )

        all_findings = tuple(
            finding for challenge in challenges for finding in challenge.findings
        )
        finding_codes = [finding.code for finding in all_findings]
        if len(finding_codes) != len(set(finding_codes)):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "challenge codes must be globally unique for deterministic resolution",
            )
        if any(finding.claim_digest not in proposal.claim_digests for finding in all_findings):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "challenger referenced a claim outside the proposal",
            )

        checked_evidence = set(evidence.checked_evidence_digests)
        if not set(proposal.evidence_digests).issubset(checked_evidence):
            return decide(
                AdversarialVerificationStatus.INCONCLUSIVE,
                "not all proposal evidence was independently checked",
            )
        if not set(evidence.unsupported_claim_digests).issubset(set(proposal.claim_digests)):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "evidence verifier referenced an unknown unsupported claim",
            )

        resolution_map = {
            resolution.challenge_code: resolution
            for resolution in evidence.challenge_resolutions
        }
        if not set(resolution_map).issubset(set(finding_codes)):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "evidence verifier resolved an unknown challenge",
            )
        for resolution in evidence.challenge_resolutions:
            if not set(resolution.evidence_digests).issubset(checked_evidence):
                return decide(
                    AdversarialVerificationStatus.REJECTED,
                    (
                        "challenge resolution cites evidence that was not "
                        "independently checked"
                    ),
                )

        if evidence.rejected_evidence_digests or evidence.unsupported_claim_digests:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                (
                    "independent evidence verification rejected provenance "
                    "or found unsupported claims"
                ),
            )
        if evidence.status is EvidenceVerificationStatus.FAIL:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "independent evidence verification failed",
            )
        if review.status is ReviewStatus.FAIL:
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "independent review failed",
            )

        blocking_codes = {finding.code for finding in all_findings if finding.blocking}
        if blocking_codes - set(resolution_map):
            return decide(
                AdversarialVerificationStatus.INCONCLUSIVE,
                "one or more blocking challenges remain unresolved",
            )
        if any(
            resolution_map[code].status is ChallengeResolutionStatus.UPHELD
            for code in blocking_codes
        ):
            return decide(
                AdversarialVerificationStatus.REJECTED,
                "independent evidence verification upheld a blocking challenge",
            )
        if any(
            resolution_map[code].status is ChallengeResolutionStatus.INCONCLUSIVE
            for code in blocking_codes
        ):
            return decide(
                AdversarialVerificationStatus.INCONCLUSIVE,
                "a blocking challenge remains evidence-inconclusive",
            )
        if (
            evidence.status is EvidenceVerificationStatus.INCONCLUSIVE
            or review.status is ReviewStatus.INCONCLUSIVE
        ):
            return decide(
                AdversarialVerificationStatus.INCONCLUSIVE,
                "independent verification or review remains inconclusive",
            )

        return decide(
            AdversarialVerificationStatus.VERIFIED,
            (
                "independent evidence verification and review passed with "
                "all blocking challenges resolved"
            ),
        )
