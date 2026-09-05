"""Program-level certification gate that composes engineering, KQM, review, and E2E evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from agents.certification import AgentCertificationReport, AgentCertificationStatus
from core.models.ids import AgentId
from validation.independent_evaluation import ReviewOutcome

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class CertificationProgramStatus(StrEnum):
    EVALUATED = "evaluated"
    PENDING_EXTERNAL_REVIEW = "pending_external_review"
    CERTIFIED = "certified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CertificationProgramEvidence:
    validated_sha: str
    expected_contract_sha256: str
    engineering_validated: bool
    e2e_suite_passed: bool
    e2e_report_sha256: str
    independent_review_required: bool = True

    def __post_init__(self) -> None:
        validated_sha = self.validated_sha.strip().lower()
        contract_sha = self.expected_contract_sha256.strip().lower()
        e2e_sha = self.e2e_report_sha256.strip().lower()
        if not _GIT_SHA_RE.fullmatch(validated_sha):
            raise ValueError("validated_sha must be a full hexadecimal commit SHA")
        if not _SHA256_RE.fullmatch(contract_sha):
            raise ValueError("expected_contract_sha256 must be a SHA-256 digest")
        if not _SHA256_RE.fullmatch(e2e_sha):
            raise ValueError("e2e_report_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "validated_sha", validated_sha)
        object.__setattr__(self, "expected_contract_sha256", contract_sha)
        object.__setattr__(self, "e2e_report_sha256", e2e_sha)


@dataclass(frozen=True, slots=True)
class CertificationProgramReport:
    agent_name: str
    agent_version: str
    contract_sha256: str
    validated_sha: str
    analytical_status: AgentCertificationStatus
    external_review: ReviewOutcome
    independent_review_required: bool
    engineering_validated: bool
    e2e_suite_passed: bool
    e2e_report_sha256: str
    status: CertificationProgramStatus
    failures: tuple[str, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "analytical_status": self.analytical_status.value,
            "contract_sha256": self.contract_sha256,
            "e2e_report_sha256": self.e2e_report_sha256,
            "e2e_suite_passed": self.e2e_suite_passed,
            "engineering_validated": self.engineering_validated,
            "external_review": self.external_review.value,
            "failures": list(self.failures),
            "independent_review_required": self.independent_review_required,
            "status": self.status.value,
            "validated_sha": self.validated_sha,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class AgentCertificationProgram:
    """Never elevate an agent above the weakest mandatory certification dimension."""

    def evaluate(
        self,
        analytical_report: AgentCertificationReport,
        evidence: CertificationProgramEvidence,
    ) -> CertificationProgramReport:
        failures: list[str] = []
        if analytical_report.contract_sha256 != evidence.expected_contract_sha256:
            failures.append("CONTRACT_DIGEST_MISMATCH")
        if not evidence.engineering_validated:
            failures.append("ENGINEERING_VALIDATION_REQUIRED")
        if not evidence.e2e_suite_passed:
            failures.append("E2E_SUITE_REQUIRED")

        if analytical_report.status is AgentCertificationStatus.REJECTED:
            failures.append("ANALYTICAL_CERTIFICATION_REJECTED")
            failures.extend(analytical_report.failures)
        elif analytical_report.status is AgentCertificationStatus.EVALUATED:
            failures.append("ANALYTICAL_CERTIFICATION_INCOMPLETE")

        if analytical_report.external_review is ReviewOutcome.FAIL:
            failures.append("INDEPENDENT_REVIEW_FAILED")

        hard_failures = tuple(sorted(set(failures)))
        if hard_failures:
            status = CertificationProgramStatus.REJECTED
        elif (
            evidence.independent_review_required
            and analytical_report.external_review is not ReviewOutcome.PASS
        ):
            status = CertificationProgramStatus.PENDING_EXTERNAL_REVIEW
        elif (
            evidence.independent_review_required
            and analytical_report.status is AgentCertificationStatus.PENDING_EXTERNAL_REVIEW
        ):
            status = CertificationProgramStatus.PENDING_EXTERNAL_REVIEW
        elif analytical_report.status is AgentCertificationStatus.CERTIFIED:
            status = CertificationProgramStatus.CERTIFIED
        else:
            status = CertificationProgramStatus.EVALUATED

        return CertificationProgramReport(
            agent_name=analytical_report.agent_name,
            agent_version=analytical_report.agent_version,
            contract_sha256=analytical_report.contract_sha256,
            validated_sha=evidence.validated_sha,
            analytical_status=analytical_report.status,
            external_review=analytical_report.external_review,
            independent_review_required=evidence.independent_review_required,
            engineering_validated=evidence.engineering_validated,
            e2e_suite_passed=evidence.e2e_suite_passed,
            e2e_report_sha256=evidence.e2e_report_sha256,
            status=status,
            failures=hard_failures,
        )


def router_certification_update(
    agent_id: AgentId,
    report: CertificationProgramReport,
) -> dict[tuple[str, str], AgentCertificationStatus]:
    """Return router eligibility only for a fully certified program outcome.

    The function deliberately returns an ordinary mapping instead of mutating a router or
    registry. A caller may apply the mapping at the controlled routing boundary after the
    certification evidence itself has been accepted.
    """

    if report.status is not CertificationProgramStatus.CERTIFIED:
        return {}
    return {
        (str(agent_id), report.agent_version): AgentCertificationStatus.CERTIFIED,
    }
