"""PVE-01 reproducible evidence over the converged Product runtime.

This module is verification/measurement-only. It consumes already-built
``ProductRuntimeRunV1`` values and never writes Canonical Case Ledger history or promotes
measurement evidence into Gold/certification authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from core.case_ledger import CaseId, ContentAddress
from core.product_runtime_v1 import (
    ProductRuntimeProofV1,
    ProductRuntimeRunV1,
    ProductRuntimeV1Error,
)
from reasoning.models import ReasoningOutcome

PVE_REGISTRY_SCHEMA_V1 = "lukart.product-verification-registry.v1"
PVE_RESULT_SCHEMA_V1 = "lukart.product-verification-result.v1"
PVE_REPORT_SCHEMA_V1 = "lukart.product-verification-report.v1"


class ProductVerificationEvidenceV1Error(ValueError):
    """Fail-closed PVE-01 verification contract violation."""


class ProductVerificationCheckId(StrEnum):
    SUPPORTED_CONCLUSION = "SUPPORTED_CONCLUSION"
    ABSTAIN_OPEN_QUESTIONS = "ABSTAIN_OPEN_QUESTIONS"
    TAMPER_REJECTION = "TAMPER_REJECTION"
    CROSS_CASE_REJECTION = "CROSS_CASE_REJECTION"
    EVIDENCE_DETERMINISM = "EVIDENCE_DETERMINISM"


class ProductVerificationOutcome(StrEnum):
    PASS = "PASS"


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise ProductVerificationEvidenceV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProductVerificationEvidenceV1Error(f"{field_name} contains control characters")
    return value


def _git_object_id(value: str, *, field_name: str) -> str:
    normalized = _identifier(value, field_name=field_name)
    if len(normalized) not in (40, 64) or normalized != normalized.lower():
        raise ProductVerificationEvidenceV1Error(
            f"{field_name} must be a lowercase 40- or 64-hex Git object id"
        )
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ProductVerificationEvidenceV1Error(
            f"{field_name} must be a lowercase 40- or 64-hex Git object id"
        ) from exc
    return normalized


@dataclass(frozen=True, slots=True)
class ProductVerificationDefinitionV1:
    check_id: ProductVerificationCheckId
    statement: str
    verifier_version: str

    def __post_init__(self) -> None:
        _identifier(self.statement, field_name="verification statement")
        _identifier(self.verifier_version, field_name="verifier_version")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id.value,
            "statement": self.statement,
            "verifier_version": self.verifier_version,
        }


def _reference_definitions() -> tuple[ProductVerificationDefinitionV1, ...]:
    definitions = (
        ProductVerificationDefinitionV1(
            ProductVerificationCheckId.SUPPORTED_CONCLUSION,
            "A supported exact Product runtime chain concludes and remains fully verifiable.",
            "pve01.supported-conclusion.v1",
        ),
        ProductVerificationDefinitionV1(
            ProductVerificationCheckId.ABSTAIN_OPEN_QUESTIONS,
            "Unresolved support produces deterministic ABSTAIN with explicit open questions.",
            "pve01.abstain-open-questions.v1",
        ),
        ProductVerificationDefinitionV1(
            ProductVerificationCheckId.TAMPER_REJECTION,
            "A content-address-consistent proof with a substituted reasoning digest is rejected.",
            "pve01.tamper-rejection.v1",
        ),
        ProductVerificationDefinitionV1(
            ProductVerificationCheckId.CROSS_CASE_REJECTION,
            "A content-address-consistent proof substituted into another case is rejected.",
            "pve01.cross-case-rejection.v1",
        ),
        ProductVerificationDefinitionV1(
            ProductVerificationCheckId.EVIDENCE_DETERMINISM,
            "Repeated verification of exact inputs produces the same evidence identities.",
            "pve01.evidence-determinism.v1",
        ),
    )
    return tuple(sorted(definitions, key=lambda item: item.check_id.value))


@dataclass(frozen=True, slots=True)
class ProductVerificationRegistryV1:
    definitions: tuple[ProductVerificationDefinitionV1, ...]
    registry_identity: ContentAddress
    schema: str = PVE_REGISTRY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PVE_REGISTRY_SCHEMA_V1:
            raise ProductVerificationEvidenceV1Error(
                f"unsupported Product verification registry schema: {self.schema}"
            )
        if self.definitions != _reference_definitions():
            raise ProductVerificationEvidenceV1Error(
                "Product verification registry must contain the exact PVE-01 reference set"
            )
        self.verify()

    @classmethod
    def reference(cls) -> ProductVerificationRegistryV1:
        definitions = _reference_definitions()
        body = cls._body(definitions)
        return cls(
            definitions=definitions,
            registry_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        definitions: tuple[ProductVerificationDefinitionV1, ...],
    ) -> dict[str, object]:
        return {
            "schema": PVE_REGISTRY_SCHEMA_V1,
            "definitions": [item.canonical_dict() for item in definitions],
            "authority": "measurement-only",
            "promotion_semantics": "no-gold-or-certification-promotion",
            "failure_semantics": "fail-closed-no-partial-pass",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(self.definitions)

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "registry_identity": self.registry_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.registry_identity != ContentAddress.for_value(self.canonical_body()):
            raise ProductVerificationEvidenceV1Error(
                "Product verification registry content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ProductVerificationInputsV1:
    supported_run: ProductRuntimeRunV1
    abstain_run: ProductRuntimeRunV1

    def verify(self) -> None:
        self.supported_run.verify()
        self.abstain_run.verify()
        if self.supported_run.proof.reasoning_outcome is not ReasoningOutcome.CONCLUDE:
            raise ProductVerificationEvidenceV1Error(
                "supported_run must have deterministic CONCLUDE outcome"
            )
        if self.abstain_run.proof.reasoning_outcome is not ReasoningOutcome.ABSTAIN:
            raise ProductVerificationEvidenceV1Error(
                "abstain_run must have deterministic ABSTAIN outcome"
            )
        if not self.abstain_run.reasoning_result.open_questions:
            raise ProductVerificationEvidenceV1Error(
                "abstain_run must expose at least one explicit open question"
            )


@dataclass(frozen=True, slots=True)
class ProductVerificationResultV1:
    check_id: ProductVerificationCheckId
    evidence_identity: ContentAddress
    result_identity: ContentAddress
    outcome: ProductVerificationOutcome = ProductVerificationOutcome.PASS
    schema: str = PVE_RESULT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PVE_RESULT_SCHEMA_V1:
            raise ProductVerificationEvidenceV1Error(
                f"unsupported Product verification result schema: {self.schema}"
            )
        if self.outcome is not ProductVerificationOutcome.PASS:
            raise ProductVerificationEvidenceV1Error(
                "failed Product verification cannot enter a PASS report"
            )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        check_id: ProductVerificationCheckId,
        evidence: dict[str, object],
    ) -> ProductVerificationResultV1:
        evidence_identity = ContentAddress.for_value(
            {
                "schema": "lukart.product-verification-evidence.v1",
                "check_id": check_id.value,
                "evidence": evidence,
            }
        )
        body = cls._body(check_id=check_id, evidence_identity=evidence_identity)
        return cls(
            check_id=check_id,
            evidence_identity=evidence_identity,
            result_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        check_id: ProductVerificationCheckId,
        evidence_identity: ContentAddress,
    ) -> dict[str, object]:
        return {
            "schema": PVE_RESULT_SCHEMA_V1,
            "check_id": check_id.value,
            "outcome": ProductVerificationOutcome.PASS.value,
            "evidence_identity": evidence_identity.canonical_dict(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            check_id=self.check_id,
            evidence_identity=self.evidence_identity,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "result_identity": self.result_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.result_identity != ContentAddress.for_value(self.canonical_body()):
            raise ProductVerificationEvidenceV1Error(
                f"Product verification result identity mismatch: {self.check_id.value}"
            )


@dataclass(frozen=True, slots=True)
class ProductVerificationReportV1:
    code_sha: str
    registry_identity: ContentAddress
    supported_proof_identity: ContentAddress
    abstain_proof_identity: ContentAddress
    results: tuple[ProductVerificationResultV1, ...]
    report_identity: ContentAddress
    outcome: ProductVerificationOutcome = ProductVerificationOutcome.PASS
    schema: str = PVE_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PVE_REPORT_SCHEMA_V1:
            raise ProductVerificationEvidenceV1Error(
                f"unsupported Product verification report schema: {self.schema}"
            )
        _git_object_id(self.code_sha, field_name="code_sha")
        reference = ProductVerificationRegistryV1.reference()
        if self.registry_identity != reference.registry_identity:
            raise ProductVerificationEvidenceV1Error(
                "Product verification registry identity mismatch"
            )
        expected_ids = tuple(item.check_id for item in reference.definitions)
        actual_ids = tuple(item.check_id for item in self.results)
        if actual_ids != expected_ids:
            raise ProductVerificationEvidenceV1Error(
                "Product verification report is missing, duplicated or reorders required checks"
            )
        for result in self.results:
            result.verify()
        self.verify()

    @staticmethod
    def _body(
        *,
        code_sha: str,
        registry_identity: ContentAddress,
        supported_proof_identity: ContentAddress,
        abstain_proof_identity: ContentAddress,
        results: tuple[ProductVerificationResultV1, ...],
    ) -> dict[str, object]:
        return {
            "schema": PVE_REPORT_SCHEMA_V1,
            "code_sha": code_sha,
            "registry_identity": registry_identity.canonical_dict(),
            "supported_proof_identity": supported_proof_identity.canonical_dict(),
            "abstain_proof_identity": abstain_proof_identity.canonical_dict(),
            "outcome": ProductVerificationOutcome.PASS.value,
            "results": [result.canonical_dict() for result in results],
            "authority": "measurement-only",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            code_sha=self.code_sha,
            registry_identity=self.registry_identity,
            supported_proof_identity=self.supported_proof_identity,
            abstain_proof_identity=self.abstain_proof_identity,
            results=self.results,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "report_identity": self.report_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.report_identity != ContentAddress.for_value(self.canonical_body()):
            raise ProductVerificationEvidenceV1Error(
                "Product verification report content-address mismatch"
            )


def _run_identity_evidence(run: ProductRuntimeRunV1) -> dict[str, object]:
    run.verify()
    proof = run.proof
    return {
        "case_id": proof.case_id.value,
        "ledger_head": proof.ledger_head.canonical_dict() if proof.ledger_head else None,
        "runtime_identity_digest": proof.runtime_identity_digest.canonical_dict(),
        "replay_manifest_identity": proof.replay_manifest_identity.canonical_dict(),
        "replay_bundle_identity": proof.replay_bundle_identity.canonical_dict(),
        "reasoning_result_digest": proof.reasoning_result_digest,
        "reasoning_outcome": proof.reasoning_outcome.value,
        "proof_identity": proof.proof_identity.canonical_dict(),
    }


def _supported_result(run: ProductRuntimeRunV1) -> ProductVerificationResultV1:
    if run.proof.reasoning_outcome is not ReasoningOutcome.CONCLUDE:
        raise ProductVerificationEvidenceV1Error("supported conclusion check did not conclude")
    return ProductVerificationResultV1.build(
        check_id=ProductVerificationCheckId.SUPPORTED_CONCLUSION,
        evidence=_run_identity_evidence(run),
    )


def _abstain_result(run: ProductRuntimeRunV1) -> ProductVerificationResultV1:
    if run.proof.reasoning_outcome is not ReasoningOutcome.ABSTAIN:
        raise ProductVerificationEvidenceV1Error("ABSTAIN check did not abstain")
    questions = run.reasoning_result.open_questions
    if not questions:
        raise ProductVerificationEvidenceV1Error("ABSTAIN check has no open questions")
    evidence = _run_identity_evidence(run)
    evidence["open_questions"] = [question.canonical_dict() for question in questions]
    return ProductVerificationResultV1.build(
        check_id=ProductVerificationCheckId.ABSTAIN_OPEN_QUESTIONS,
        evidence=evidence,
    )


def _tampered_reasoning_proof(proof: ProductRuntimeProofV1) -> ProductRuntimeProofV1:
    substituted_digest = "f" * 64
    if proof.reasoning_result_digest == substituted_digest:
        substituted_digest = "e" * 64
    body = proof.canonical_body()
    body["reasoning_result_digest"] = substituted_digest
    return replace(
        proof,
        reasoning_result_digest=substituted_digest,
        proof_identity=ContentAddress.for_value(body),
    )


def _tamper_rejection_result(run: ProductRuntimeRunV1) -> ProductVerificationResultV1:
    tampered = replace(run, proof=_tampered_reasoning_proof(run.proof))
    try:
        tampered.verify()
    except ProductRuntimeV1Error:
        return ProductVerificationResultV1.build(
            check_id=ProductVerificationCheckId.TAMPER_REJECTION,
            evidence={
                "source_proof_identity": run.proof.proof_identity.canonical_dict(),
                "tampered_proof_identity": tampered.proof.proof_identity.canonical_dict(),
                "rejection": "ProductRuntimeV1Error",
                "tamper": "reasoning_result_digest_substitution",
            },
        )
    raise ProductVerificationEvidenceV1Error(
        "tampered Product runtime proof was unexpectedly accepted"
    )


def _foreign_case_id(case_id: CaseId) -> CaseId:
    return CaseId(f"{case_id.value}-PVE-FOREIGN")


def _cross_case_rejection_result(run: ProductRuntimeRunV1) -> ProductVerificationResultV1:
    foreign_case = _foreign_case_id(run.proof.case_id)
    body = run.proof.canonical_body()
    body["case_id"] = foreign_case.value
    forged_proof = replace(
        run.proof,
        case_id=foreign_case,
        proof_identity=ContentAddress.for_value(body),
    )
    forged = replace(run, proof=forged_proof)
    try:
        forged.verify()
    except ProductRuntimeV1Error:
        return ProductVerificationResultV1.build(
            check_id=ProductVerificationCheckId.CROSS_CASE_REJECTION,
            evidence={
                "source_case_id": run.proof.case_id.value,
                "foreign_case_id": foreign_case.value,
                "source_proof_identity": run.proof.proof_identity.canonical_dict(),
                "forged_proof_identity": forged_proof.proof_identity.canonical_dict(),
                "rejection": "ProductRuntimeV1Error",
            },
        )
    raise ProductVerificationEvidenceV1Error(
        "cross-case Product runtime proof substitution was unexpectedly accepted"
    )


def _evidence_determinism_result(
    supported: ProductRuntimeRunV1,
    abstain: ProductRuntimeRunV1,
) -> ProductVerificationResultV1:
    first = (
        _supported_result(supported).evidence_identity,
        _abstain_result(abstain).evidence_identity,
        _tamper_rejection_result(supported).evidence_identity,
        _cross_case_rejection_result(supported).evidence_identity,
    )
    second = (
        _supported_result(supported).evidence_identity,
        _abstain_result(abstain).evidence_identity,
        _tamper_rejection_result(supported).evidence_identity,
        _cross_case_rejection_result(supported).evidence_identity,
    )
    if first != second:
        raise ProductVerificationEvidenceV1Error(
            "repeated Product verification evidence identity mismatch"
        )
    return ProductVerificationResultV1.build(
        check_id=ProductVerificationCheckId.EVIDENCE_DETERMINISM,
        evidence={"evidence_identities": [item.canonical_dict() for item in first]},
    )


def verify_product_evidence_v1(
    *,
    inputs: ProductVerificationInputsV1,
    code_sha: str,
    expected_code_sha: str,
) -> ProductVerificationReportV1:
    """Run the exact PVE-01 registry and return a complete content-addressed PASS report."""

    actual_sha = _git_object_id(code_sha, field_name="code_sha")
    expected_sha = _git_object_id(expected_code_sha, field_name="expected_code_sha")
    if actual_sha != expected_sha:
        raise ProductVerificationEvidenceV1Error(
            "code_sha does not match the externally expected exact candidate SHA"
        )

    inputs.verify()
    registry = ProductVerificationRegistryV1.reference()
    by_id = {
        ProductVerificationCheckId.SUPPORTED_CONCLUSION: _supported_result(
            inputs.supported_run
        ),
        ProductVerificationCheckId.ABSTAIN_OPEN_QUESTIONS: _abstain_result(
            inputs.abstain_run
        ),
        ProductVerificationCheckId.TAMPER_REJECTION: _tamper_rejection_result(
            inputs.supported_run
        ),
        ProductVerificationCheckId.CROSS_CASE_REJECTION: _cross_case_rejection_result(
            inputs.supported_run
        ),
        ProductVerificationCheckId.EVIDENCE_DETERMINISM: _evidence_determinism_result(
            inputs.supported_run,
            inputs.abstain_run,
        ),
    }
    results = tuple(by_id[item.check_id] for item in registry.definitions)
    body = ProductVerificationReportV1._body(
        code_sha=actual_sha,
        registry_identity=registry.registry_identity,
        supported_proof_identity=inputs.supported_run.proof.proof_identity,
        abstain_proof_identity=inputs.abstain_run.proof.proof_identity,
        results=results,
    )
    return ProductVerificationReportV1(
        code_sha=actual_sha,
        registry_identity=registry.registry_identity,
        supported_proof_identity=inputs.supported_run.proof.proof_identity,
        abstain_proof_identity=inputs.abstain_run.proof.proof_identity,
        results=results,
        report_identity=ContentAddress.for_value(body),
    )
