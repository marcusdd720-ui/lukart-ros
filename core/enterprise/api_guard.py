"""E8 stable Enterprise API guard around the existing P3 digest-bound API surface."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import canonical_json, content_digest

from .authorization import AuthorizationEngine, ResourceDescriptor
from .contracts import (
    AttestationPurpose,
    AttestationVerifier,
    AuthorizationContext,
    EnterpriseContractError,
    Permission,
    SignedAttestation,
)


class ApiOperation(StrEnum):
    READ = "READ"
    MUTATE = "MUTATE"
    TRUST_PROMOTE = "TRUST_PROMOTE"


@dataclass(frozen=True, slots=True)
class EnterpriseRequest:
    request_id: str
    api_version: str
    tenant_id: str
    operation: ApiOperation
    permission: Permission
    payload: Mapping[str, object]
    nonce: str
    idempotency_key: str | None = None
    attestation: SignedAttestation | None = None

    def __post_init__(self) -> None:
        for value, field in (
            (self.request_id, "request_id"),
            (self.api_version, "api_version"),
            (self.tenant_id, "tenant_id"),
            (self.nonce, "nonce"),
        ):
            if not value.strip():
                raise EnterpriseContractError(f"{field} is required")
        if self.operation is not ApiOperation.READ:
            if self.idempotency_key is None or not self.idempotency_key.strip():
                raise EnterpriseContractError("mutating requests require idempotency_key")
        if (
            self.operation is ApiOperation.TRUST_PROMOTE
            and self.permission is not Permission.TRUST_PROMOTE
        ):
            raise EnterpriseContractError(
                "TRUST_PROMOTE operation requires trust:promote permission"
            )

    def canonical_body(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "api_version": self.api_version,
            "tenant_id": self.tenant_id,
            "operation": self.operation.value,
            "permission": self.permission.value,
            "payload": dict(self.payload),
            "nonce": self.nonce,
            "idempotency_key": self.idempotency_key,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_body())


@dataclass(frozen=True, slots=True)
class ApiReceipt:
    request_digest: str
    authorization_digest: str
    subject_id: str
    accepted: bool
    attestation_digest: str | None

    def digest(self) -> str:
        return content_digest(
            {
                "request_digest": self.request_digest,
                "authorization_digest": self.authorization_digest,
                "subject_id": self.subject_id,
                "accepted": self.accepted,
                "attestation_digest": self.attestation_digest,
            }
        )


class EnterpriseApiGuard:
    def __init__(
        self,
        authorization: AuthorizationEngine,
        *,
        verifier: AttestationVerifier | None = None,
        supported_versions: tuple[str, ...] = ("1.0.0",),
        max_payload_bytes: int = 1_000_000,
        rate_limit: int = 100,
        rate_window_seconds: int = 60,
    ) -> None:
        if max_payload_bytes < 1 or rate_limit < 1 or rate_window_seconds < 1:
            raise EnterpriseContractError("invalid API guard bounds")
        if not supported_versions:
            raise EnterpriseContractError("at least one API version is required")
        self.authorization = authorization
        self.verifier = verifier
        self.supported_versions = frozenset(supported_versions)
        self.max_payload_bytes = max_payload_bytes
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self._nonces: set[tuple[str, str]] = set()
        self._idempotency: dict[tuple[str, str], tuple[str, ApiReceipt]] = {}
        self._rate: dict[str, deque[int]] = defaultdict(deque)

    def _check_rate(self, subject_id: str, now: int) -> None:
        bucket = self._rate[subject_id]
        cutoff = now - self.rate_window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.rate_limit:
            raise EnterpriseContractError("API rate quota exceeded")
        bucket.append(now)

    def process(
        self,
        request: EnterpriseRequest,
        context: AuthorizationContext,
        resource: ResourceDescriptor,
        *,
        now: int,
    ) -> ApiReceipt:
        if request.api_version not in self.supported_versions:
            raise EnterpriseContractError("unsupported Enterprise API version")
        if request.tenant_id != context.tenant_id or resource.tenant_id != context.tenant_id:
            raise EnterpriseContractError("API tenant mismatch")
        payload_size = len(canonical_json(dict(request.payload)).encode("utf-8"))
        if payload_size > self.max_payload_bytes:
            raise EnterpriseContractError("API payload size limit exceeded")

        request_digest = request.digest()
        idempotency_slot: tuple[str, str] | None = None
        if request.idempotency_key is not None:
            idempotency_slot = (context.subject_id, request.idempotency_key)
            previous = self._idempotency.get(idempotency_slot)
            if previous is not None:
                previous_digest, previous_receipt = previous
                if previous_digest != request_digest:
                    raise EnterpriseContractError("idempotency key reused for different request")
                return previous_receipt

        nonce_slot = (context.subject_id, request.nonce)
        if nonce_slot in self._nonces:
            raise EnterpriseContractError("API replay nonce already used")
        self._check_rate(context.subject_id, now)

        decision = self.authorization.require(context, request.permission, resource)
        attestation_digest: str | None = None
        if request.operation is ApiOperation.TRUST_PROMOTE:
            if self.verifier is None or request.attestation is None:
                raise EnterpriseContractError("trusted-state mutation requires attestation")
            attestation_digest = self.verifier.verify(
                request.attestation,
                expected_purpose=AttestationPurpose.API_TRUST,
                expected_subject_digest=request_digest,
                payload=request.payload,
                now=now,
            )

        self._nonces.add(nonce_slot)
        receipt = ApiReceipt(
            request_digest=request_digest,
            authorization_digest=decision.digest(),
            subject_id=context.subject_id,
            accepted=True,
            attestation_digest=attestation_digest,
        )
        if idempotency_slot is not None:
            self._idempotency[idempotency_slot] = (request_digest, receipt)
        return receipt
