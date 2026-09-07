"""XCH-01 signed, offline-verifiable Case Replay exchange envelope v1.

The exchange envelope is a transport/provenance artifact, never another truth store.
It delegates case integrity and projection rebuild to Case Replay v2, binds explicit
source/recipient authorization evidence, and uses the existing Enterprise Ed25519
attestation contract. Verification is offline and exposes no Canonical Case Ledger
write path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.case_ledger.contracts import CaseId, ContentAddress
from core.case_replay_v2 import (
    CaseReplayBundleV2,
    CaseReplayManifestV2,
    CaseReplayV2Error,
    CaseReplayVerificationV2,
    verify_case_replay_bundle,
)
from core.enterprise.authorization import AuthorizationDecision, ResourceDescriptor
from core.enterprise.contracts import (
    AttestationPurpose,
    AttestationSigner,
    AttestationVerifier,
    DataClassification,
    Permission,
    SignedAttestation,
)
from core.p3.contracts import canonical_json, require_hex_digest

CASE_EXCHANGE_REQUEST_SCHEMA_V1 = "lukart.case-exchange-request.v1"
CASE_EXCHANGE_AUTHORIZATION_SCHEMA_V1 = "lukart.case-exchange-authorization.v1"
CASE_EXCHANGE_BUNDLE_SCHEMA_V1 = "lukart.signed-case-exchange.v1"
CASE_EXCHANGE_ATTESTATION_DOMAIN_V1 = "lukart.case-exchange.attestation-domain.v1"
CASE_EXCHANGE_SEMANTICS_V1 = "origin-integrity-only-not-epistemic-truth"
AUTHORIZATION_DECISION_SCHEMA_V2 = "lukart.authorization-decision.v2"

_REQUEST_KEYS = frozenset(
    {
        "schema",
        "source_tenant_id",
        "source_case_id",
        "recipient_tenant_id",
        "recipient_case_id",
        "request_identity",
    }
)
_AUTHORIZATION_KEYS = frozenset(
    {
        "schema",
        "party",
        "subject_id",
        "permission",
        "resource_id",
        "tenant_id",
        "case_id",
        "workspace_id",
        "classification",
        "reason",
        "context_digest",
        "resource_digest",
        "policy_digest",
        "request_digest",
        "decision_schema",
        "decision_digest",
        "authorization_identity",
    }
)
_ATTESTATION_KEYS = frozenset(
    {
        "key_id",
        "purpose",
        "subject_digest",
        "payload_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "signature_b64",
    }
)
_BUNDLE_KEYS = frozenset(
    {
        "schema",
        "attestation_domain",
        "semantics",
        "request",
        "replay_bundle",
        "source_authorization",
        "recipient_authorization",
        "attestation",
        "exchange_identity",
    }
)


class CaseExchangeV1Error(ValueError):
    """Fail-closed Signed Case Exchange v1 contract violation."""


class ExchangeParty(StrEnum):
    SOURCE = "SOURCE"
    RECIPIENT = "RECIPIENT"


def _copy_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise CaseExchangeV1Error(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise CaseExchangeV1Error(
            f"{field_name} is not canonically serializable"
        ) from exc
    if not isinstance(decoded, dict):
        raise CaseExchangeV1Error(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _require_exact_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    missing = tuple(sorted(expected - actual))
    unknown = tuple(sorted(actual - expected))
    if not missing and not unknown:
        return
    details: list[str] = []
    if missing:
        details.append("missing=" + ",".join(missing))
    if unknown:
        details.append("unknown=" + ",".join(unknown))
    raise CaseExchangeV1Error(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CaseExchangeV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise CaseExchangeV1Error(f"{field_name} must be a content-address object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise CaseExchangeV1Error(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class CaseExchangeRequestV1:
    source_tenant_id: str
    source_case_id: CaseId
    recipient_tenant_id: str
    recipient_case_id: CaseId
    request_identity: ContentAddress
    schema: str = CASE_EXCHANGE_REQUEST_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CASE_EXCHANGE_REQUEST_SCHEMA_V1:
            raise CaseExchangeV1Error(
                f"unsupported case exchange request schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "source_tenant_id",
            _text(self.source_tenant_id, field_name="source_tenant_id"),
        )
        object.__setattr__(
            self,
            "recipient_tenant_id",
            _text(self.recipient_tenant_id, field_name="recipient_tenant_id"),
        )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        source_tenant_id: str,
        source_case_id: CaseId,
        recipient_tenant_id: str,
        recipient_case_id: CaseId,
    ) -> CaseExchangeRequestV1:
        source_tenant = _text(source_tenant_id, field_name="source_tenant_id")
        recipient_tenant = _text(
            recipient_tenant_id,
            field_name="recipient_tenant_id",
        )
        body = cls._body(
            source_tenant_id=source_tenant,
            source_case_id=source_case_id,
            recipient_tenant_id=recipient_tenant,
            recipient_case_id=recipient_case_id,
        )
        return cls(
            source_tenant_id=source_tenant,
            source_case_id=source_case_id,
            recipient_tenant_id=recipient_tenant,
            recipient_case_id=recipient_case_id,
            request_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        source_tenant_id: str,
        source_case_id: CaseId,
        recipient_tenant_id: str,
        recipient_case_id: CaseId,
    ) -> dict[str, object]:
        return {
            "schema": CASE_EXCHANGE_REQUEST_SCHEMA_V1,
            "source_tenant_id": source_tenant_id,
            "source_case_id": source_case_id.value,
            "recipient_tenant_id": recipient_tenant_id,
            "recipient_case_id": recipient_case_id.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CaseExchangeRequestV1:
        raw = _copy_mapping(value, field_name="case exchange request")
        _require_exact_keys(
            raw,
            expected=_REQUEST_KEYS,
            field_name="case exchange request",
        )
        schema = _text(raw.get("schema"), field_name="request schema")
        source_tenant = _text(
            raw.get("source_tenant_id"),
            field_name="source_tenant_id",
        )
        recipient_tenant = _text(
            raw.get("recipient_tenant_id"),
            field_name="recipient_tenant_id",
        )
        source_case = _text(raw.get("source_case_id"), field_name="source_case_id")
        recipient_case = _text(
            raw.get("recipient_case_id"),
            field_name="recipient_case_id",
        )
        return cls(
            source_tenant_id=source_tenant,
            source_case_id=CaseId(source_case),
            recipient_tenant_id=recipient_tenant,
            recipient_case_id=CaseId(recipient_case),
            request_identity=_address(
                raw.get("request_identity"),
                field_name="request_identity",
            ),
            schema=schema,
        )

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            source_tenant_id=self.source_tenant_id,
            source_case_id=self.source_case_id,
            recipient_tenant_id=self.recipient_tenant_id,
            recipient_case_id=self.recipient_case_id,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "request_identity": self.request_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.request_identity != ContentAddress.for_value(self.canonical_body()):
            raise CaseExchangeV1Error(
                "case exchange request content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ExchangeAuthorizationV1:
    party: ExchangeParty
    subject_id: str
    permission: Permission
    resource_id: str
    tenant_id: str
    case_id: CaseId
    workspace_id: str | None
    classification: DataClassification
    reason: str
    context_digest: str
    resource_digest: str
    policy_digest: str
    request_digest: str
    decision_schema: str
    decision_digest: str
    authorization_identity: ContentAddress
    schema: str = CASE_EXCHANGE_AUTHORIZATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CASE_EXCHANGE_AUTHORIZATION_SCHEMA_V1:
            raise CaseExchangeV1Error(
                f"unsupported exchange authorization schema: {self.schema}"
            )
        if self.decision_schema != AUTHORIZATION_DECISION_SCHEMA_V2:
            raise CaseExchangeV1Error("unsupported authorization decision schema")
        for field_name in (
            "subject_id",
            "resource_id",
            "tenant_id",
            "reason",
            "decision_schema",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name=field_name),
            )
        if self.workspace_id is not None:
            object.__setattr__(
                self,
                "workspace_id",
                _text(self.workspace_id, field_name="workspace_id"),
            )
        for field_name in (
            "context_digest",
            "resource_digest",
            "policy_digest",
            "request_digest",
            "decision_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                require_hex_digest(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        party: ExchangeParty,
        decision: AuthorizationDecision,
        resource: ResourceDescriptor,
        request: CaseExchangeRequestV1,
    ) -> ExchangeAuthorizationV1:
        request.verify()
        expected_permission = cls._required_permission(party)
        expected_tenant, expected_case = cls._expected_scope(party, request)
        if not decision.allowed:
            raise CaseExchangeV1Error(
                f"{party.value.lower()} authorization is denied"
            )
        if decision.permission is not expected_permission:
            raise CaseExchangeV1Error(
                f"{party.value.lower()} authorization permission mismatch"
            )
        if decision.resource_id != resource.resource_id:
            raise CaseExchangeV1Error("authorization resource id mismatch")
        if decision.resource_digest != resource.digest():
            raise CaseExchangeV1Error("authorization resource digest mismatch")
        if decision.request_digest != request.request_identity.digest:
            raise CaseExchangeV1Error("authorization request digest mismatch")
        if resource.tenant_id != expected_tenant or resource.case_id != expected_case.value:
            raise CaseExchangeV1Error(
                f"{party.value.lower()} authorization scope mismatch"
            )
        if resource.case_id is None:
            raise CaseExchangeV1Error("case exchange authorization requires case scope")

        body = cls._body(
            party=party,
            subject_id=decision.subject_id,
            permission=decision.permission,
            resource=resource,
            reason=decision.reason,
            context_digest=decision.context_digest,
            policy_digest=decision.policy_digest,
            request_digest=decision.request_digest,
            decision_schema=decision.schema,
            decision_digest=decision.digest(),
        )
        return cls(
            party=party,
            subject_id=decision.subject_id,
            permission=decision.permission,
            resource_id=resource.resource_id,
            tenant_id=resource.tenant_id,
            case_id=CaseId(resource.case_id),
            workspace_id=resource.workspace_id,
            classification=resource.classification,
            reason=decision.reason,
            context_digest=decision.context_digest,
            resource_digest=resource.digest(),
            policy_digest=decision.policy_digest,
            request_digest=cast(str, decision.request_digest),
            decision_schema=decision.schema,
            decision_digest=decision.digest(),
            authorization_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _required_permission(party: ExchangeParty) -> Permission:
        if party is ExchangeParty.SOURCE:
            return Permission.CASE_READ
        return Permission.CASE_WRITE

    @staticmethod
    def _expected_scope(
        party: ExchangeParty,
        request: CaseExchangeRequestV1,
    ) -> tuple[str, CaseId]:
        if party is ExchangeParty.SOURCE:
            return request.source_tenant_id, request.source_case_id
        return request.recipient_tenant_id, request.recipient_case_id

    @staticmethod
    def _body(
        *,
        party: ExchangeParty,
        subject_id: str,
        permission: Permission,
        resource: ResourceDescriptor,
        reason: str,
        context_digest: str,
        policy_digest: str,
        request_digest: str | None,
        decision_schema: str,
        decision_digest: str,
    ) -> dict[str, object]:
        if request_digest is None:
            raise CaseExchangeV1Error("authorization request digest is required")
        return {
            "schema": CASE_EXCHANGE_AUTHORIZATION_SCHEMA_V1,
            "party": party.value,
            "subject_id": subject_id,
            "permission": permission.value,
            "resource_id": resource.resource_id,
            "tenant_id": resource.tenant_id,
            "case_id": resource.case_id,
            "workspace_id": resource.workspace_id,
            "classification": resource.classification.value,
            "reason": reason,
            "context_digest": context_digest,
            "resource_digest": resource.digest(),
            "policy_digest": policy_digest,
            "request_digest": request_digest,
            "decision_schema": decision_schema,
            "decision_digest": decision_digest,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
        *,
        request: CaseExchangeRequestV1,
    ) -> ExchangeAuthorizationV1:
        raw = _copy_mapping(value, field_name="case exchange authorization")
        _require_exact_keys(
            raw,
            expected=_AUTHORIZATION_KEYS,
            field_name="case exchange authorization",
        )
        try:
            party = ExchangeParty(
                _text(raw.get("party"), field_name="authorization party")
            )
            permission = Permission(
                _text(raw.get("permission"), field_name="authorization permission")
            )
            classification = DataClassification(
                _text(raw.get("classification"), field_name="classification")
            )
        except ValueError as exc:
            raise CaseExchangeV1Error(
                "exchange authorization contains unknown enum value"
            ) from exc
        case_id = _text(raw.get("case_id"), field_name="authorization case_id")
        workspace = raw.get("workspace_id")
        if workspace is not None:
            workspace = _text(workspace, field_name="workspace_id")
        record = cls(
            party=party,
            subject_id=_text(raw.get("subject_id"), field_name="subject_id"),
            permission=permission,
            resource_id=_text(raw.get("resource_id"), field_name="resource_id"),
            tenant_id=_text(raw.get("tenant_id"), field_name="tenant_id"),
            case_id=CaseId(case_id),
            workspace_id=cast(str | None, workspace),
            classification=classification,
            reason=_text(raw.get("reason"), field_name="reason"),
            context_digest=_text(
                raw.get("context_digest"),
                field_name="context_digest",
            ),
            resource_digest=_text(
                raw.get("resource_digest"),
                field_name="resource_digest",
            ),
            policy_digest=_text(
                raw.get("policy_digest"),
                field_name="policy_digest",
            ),
            request_digest=_text(
                raw.get("request_digest"),
                field_name="request_digest",
            ),
            decision_schema=_text(
                raw.get("decision_schema"),
                field_name="decision_schema",
            ),
            decision_digest=_text(
                raw.get("decision_digest"),
                field_name="decision_digest",
            ),
            authorization_identity=_address(
                raw.get("authorization_identity"),
                field_name="authorization_identity",
            ),
            schema=_text(raw.get("schema"), field_name="authorization schema"),
        )
        record.verify_for_request(request)
        return record

    def resource(self) -> ResourceDescriptor:
        return ResourceDescriptor(
            resource_id=self.resource_id,
            tenant_id=self.tenant_id,
            case_id=self.case_id.value,
            workspace_id=self.workspace_id,
            classification=self.classification,
        )

    def decision(self) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=True,
            subject_id=self.subject_id,
            permission=self.permission,
            resource_id=self.resource_id,
            reason=self.reason,
            context_digest=self.context_digest,
            resource_digest=self.resource_digest,
            policy_digest=self.policy_digest,
            request_digest=self.request_digest,
            schema=self.decision_schema,
        )

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            party=self.party,
            subject_id=self.subject_id,
            permission=self.permission,
            resource=self.resource(),
            reason=self.reason,
            context_digest=self.context_digest,
            policy_digest=self.policy_digest,
            request_digest=self.request_digest,
            decision_schema=self.decision_schema,
            decision_digest=self.decision_digest,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "authorization_identity": self.authorization_identity.canonical_dict(),
        }

    def verify_identity(self) -> None:
        if self.resource_digest != self.resource().digest():
            raise CaseExchangeV1Error("authorization resource digest mismatch")
        if self.decision_digest != self.decision().digest():
            raise CaseExchangeV1Error("authorization decision digest mismatch")
        if self.authorization_identity != ContentAddress.for_value(
            self.canonical_body()
        ):
            raise CaseExchangeV1Error(
                "exchange authorization content-address mismatch"
            )

    def verify_for_request(self, request: CaseExchangeRequestV1) -> None:
        self.verify_identity()
        request.verify()
        expected_permission = self._required_permission(self.party)
        if self.permission is not expected_permission:
            raise CaseExchangeV1Error("exchange authorization permission mismatch")
        expected_tenant, expected_case = self._expected_scope(self.party, request)
        if self.tenant_id != expected_tenant or self.case_id != expected_case:
            raise CaseExchangeV1Error("exchange authorization scope mismatch")
        if self.request_digest != request.request_identity.digest:
            raise CaseExchangeV1Error("exchange authorization request mismatch")


def _attestation_dict(attestation: SignedAttestation) -> dict[str, object]:
    return {
        "key_id": attestation.key_id,
        "purpose": attestation.purpose.value,
        "subject_digest": attestation.subject_digest,
        "payload_digest": attestation.payload_digest,
        "issued_at": attestation.issued_at,
        "expires_at": attestation.expires_at,
        "nonce": attestation.nonce,
        "signature_b64": attestation.signature_b64,
    }


def _parse_attestation(value: Mapping[str, object]) -> SignedAttestation:
    raw = _copy_mapping(value, field_name="case exchange attestation")
    _require_exact_keys(
        raw,
        expected=_ATTESTATION_KEYS,
        field_name="case exchange attestation",
    )
    try:
        purpose = AttestationPurpose(
            _text(raw.get("purpose"), field_name="attestation purpose")
        )
    except ValueError as exc:
        raise CaseExchangeV1Error("unknown attestation purpose") from exc
    issued_at = raw.get("issued_at")
    expires_at = raw.get("expires_at")
    if not isinstance(issued_at, int) or isinstance(issued_at, bool) or issued_at < 0:
        raise CaseExchangeV1Error("attestation issued_at must be a nonnegative integer")
    if expires_at is not None and (
        not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or expires_at <= issued_at
    ):
        raise CaseExchangeV1Error("attestation expires_at must be after issued_at")
    return SignedAttestation(
        key_id=_text(raw.get("key_id"), field_name="attestation key_id"),
        purpose=purpose,
        subject_digest=require_hex_digest(
            _text(raw.get("subject_digest"), field_name="attestation subject_digest"),
            field_name="attestation subject_digest",
        ),
        payload_digest=require_hex_digest(
            _text(raw.get("payload_digest"), field_name="attestation payload_digest"),
            field_name="attestation payload_digest",
        ),
        issued_at=issued_at,
        expires_at=cast(int | None, expires_at),
        nonce=_text(raw.get("nonce"), field_name="attestation nonce"),
        signature_b64=_text(
            raw.get("signature_b64"),
            field_name="attestation signature",
        ),
    )


@dataclass(frozen=True, slots=True)
class CaseExchangeVerificationV1:
    exchange_identity: ContentAddress
    request_identity: ContentAddress
    replay_manifest_identity: ContentAddress
    replay_bundle_identity: ContentAddress
    attestation_digest: str
    source_authorization_identity: ContentAddress
    recipient_authorization_identity: ContentAddress


@dataclass(frozen=True, slots=True)
class SignedCaseExchangeBundleV1:
    request: CaseExchangeRequestV1
    replay_bundle: Mapping[str, object]
    source_authorization: ExchangeAuthorizationV1
    recipient_authorization: ExchangeAuthorizationV1
    attestation: SignedAttestation
    exchange_identity: ContentAddress
    attestation_domain: str = CASE_EXCHANGE_ATTESTATION_DOMAIN_V1
    semantics: str = CASE_EXCHANGE_SEMANTICS_V1
    schema: str = CASE_EXCHANGE_BUNDLE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CASE_EXCHANGE_BUNDLE_SCHEMA_V1:
            raise CaseExchangeV1Error(
                f"unsupported signed case exchange schema: {self.schema}"
            )
        if self.attestation_domain != CASE_EXCHANGE_ATTESTATION_DOMAIN_V1:
            raise CaseExchangeV1Error("unknown case exchange attestation domain")
        if self.semantics != CASE_EXCHANGE_SEMANTICS_V1:
            raise CaseExchangeV1Error("unknown case exchange semantics")
        object.__setattr__(
            self,
            "replay_bundle",
            _copy_mapping(self.replay_bundle, field_name="replay bundle"),
        )

    @classmethod
    def build(
        cls,
        *,
        request: CaseExchangeRequestV1,
        replay_bundle: CaseReplayBundleV2,
        source_decision: AuthorizationDecision,
        source_resource: ResourceDescriptor,
        recipient_decision: AuthorizationDecision,
        recipient_resource: ResourceDescriptor,
        signer: AttestationSigner,
        issued_at: int,
        nonce: str,
        expires_at: int | None = None,
    ) -> SignedCaseExchangeBundleV1:
        request.verify()
        replay_verification = replay_bundle.verify()
        if replay_bundle.manifest.case_id != request.source_case_id:
            raise CaseExchangeV1Error(
                "replay bundle case does not match source case"
            )
        if replay_verification.manifest_identity != replay_bundle.manifest.manifest_identity:
            raise CaseExchangeV1Error("replay verification identity mismatch")
        source_authorization = ExchangeAuthorizationV1.build(
            party=ExchangeParty.SOURCE,
            decision=source_decision,
            resource=source_resource,
            request=request,
        )
        recipient_authorization = ExchangeAuthorizationV1.build(
            party=ExchangeParty.RECIPIENT,
            decision=recipient_decision,
            resource=recipient_resource,
            request=request,
        )
        replay_snapshot = _copy_mapping(
            replay_bundle.canonical_dict(),
            field_name="replay bundle",
        )
        unsigned_body = cls._unsigned_body(
            request=request,
            replay_bundle=replay_snapshot,
            source_authorization=source_authorization,
            recipient_authorization=recipient_authorization,
        )
        attestation = signer.sign(
            purpose=AttestationPurpose.PROVENANCE,
            subject_digest=replay_bundle.bundle_identity.digest,
            payload=unsigned_body,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=_text(nonce, field_name="exchange nonce"),
        )
        signed_body = {
            **unsigned_body,
            "attestation": _attestation_dict(attestation),
        }
        return cls(
            request=request,
            replay_bundle=replay_snapshot,
            source_authorization=source_authorization,
            recipient_authorization=recipient_authorization,
            attestation=attestation,
            exchange_identity=ContentAddress.for_value(signed_body),
        )

    @staticmethod
    def _unsigned_body(
        *,
        request: CaseExchangeRequestV1,
        replay_bundle: Mapping[str, object],
        source_authorization: ExchangeAuthorizationV1,
        recipient_authorization: ExchangeAuthorizationV1,
    ) -> dict[str, object]:
        return {
            "schema": CASE_EXCHANGE_BUNDLE_SCHEMA_V1,
            "attestation_domain": CASE_EXCHANGE_ATTESTATION_DOMAIN_V1,
            "semantics": CASE_EXCHANGE_SEMANTICS_V1,
            "request": request.canonical_dict(),
            "replay_bundle": dict(replay_bundle),
            "source_authorization": source_authorization.canonical_dict(),
            "recipient_authorization": recipient_authorization.canonical_dict(),
        }

    def canonical_unsigned_body(self) -> dict[str, object]:
        return self._unsigned_body(
            request=self.request,
            replay_bundle=self.replay_bundle,
            source_authorization=self.source_authorization,
            recipient_authorization=self.recipient_authorization,
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            **self.canonical_unsigned_body(),
            "attestation": _attestation_dict(self.attestation),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "exchange_identity": self.exchange_identity.canonical_dict(),
        }

    def verify(
        self,
        *,
        verifier: AttestationVerifier,
        now: int,
    ) -> CaseExchangeVerificationV1:
        return verify_signed_case_exchange(
            self.canonical_dict(),
            verifier=verifier,
            now=now,
        )


def _replay_manifest(
    replay_raw: Mapping[str, object],
) -> tuple[CaseReplayManifestV2, ContentAddress, CaseReplayVerificationV2]:
    try:
        verification = verify_case_replay_bundle(replay_raw)
        raw_manifest = replay_raw.get("manifest")
        if not isinstance(raw_manifest, Mapping):
            raise CaseExchangeV1Error("replay bundle manifest is malformed")
        manifest = CaseReplayManifestV2.from_dict(
            cast(Mapping[str, object], raw_manifest)
        )
    except CaseReplayV2Error as exc:
        raise CaseExchangeV1Error(str(exc)) from exc
    replay_identity = _address(
        replay_raw.get("bundle_identity"),
        field_name="replay bundle identity",
    )
    return manifest, replay_identity, verification


def verify_signed_case_exchange(
    value: Mapping[str, object],
    *,
    verifier: AttestationVerifier,
    now: int,
) -> CaseExchangeVerificationV1:
    """Verify a signed exchange entirely from envelope bytes and trusted public keys."""

    raw = _copy_mapping(value, field_name="signed case exchange")
    _require_exact_keys(
        raw,
        expected=_BUNDLE_KEYS,
        field_name="signed case exchange",
    )
    if raw.get("schema") != CASE_EXCHANGE_BUNDLE_SCHEMA_V1:
        raise CaseExchangeV1Error(
            f"unsupported signed case exchange schema: {raw.get('schema')}"
        )
    if raw.get("attestation_domain") != CASE_EXCHANGE_ATTESTATION_DOMAIN_V1:
        raise CaseExchangeV1Error("unknown case exchange attestation domain")
    if raw.get("semantics") != CASE_EXCHANGE_SEMANTICS_V1:
        raise CaseExchangeV1Error("unknown case exchange semantics")

    request_raw = raw.get("request")
    replay_raw = raw.get("replay_bundle")
    source_raw = raw.get("source_authorization")
    recipient_raw = raw.get("recipient_authorization")
    attestation_raw = raw.get("attestation")
    if any(
        not isinstance(item, Mapping)
        for item in (
            request_raw,
            replay_raw,
            source_raw,
            recipient_raw,
            attestation_raw,
        )
    ):
        raise CaseExchangeV1Error("signed case exchange contains malformed objects")

    request = CaseExchangeRequestV1.from_dict(
        cast(Mapping[str, object], request_raw)
    )
    replay_mapping = cast(Mapping[str, object], replay_raw)
    manifest, replay_identity, replay_verification = _replay_manifest(
        replay_mapping
    )
    if manifest.case_id != request.source_case_id:
        raise CaseExchangeV1Error(
            "replay bundle case does not match source case"
        )
    source_authorization = ExchangeAuthorizationV1.from_dict(
        cast(Mapping[str, object], source_raw),
        request=request,
    )
    recipient_authorization = ExchangeAuthorizationV1.from_dict(
        cast(Mapping[str, object], recipient_raw),
        request=request,
    )
    if source_authorization.party is not ExchangeParty.SOURCE:
        raise CaseExchangeV1Error("source authorization party mismatch")
    if recipient_authorization.party is not ExchangeParty.RECIPIENT:
        raise CaseExchangeV1Error("recipient authorization party mismatch")

    attestation = _parse_attestation(
        cast(Mapping[str, object], attestation_raw)
    )
    unsigned_body = SignedCaseExchangeBundleV1._unsigned_body(
        request=request,
        replay_bundle=replay_mapping,
        source_authorization=source_authorization,
        recipient_authorization=recipient_authorization,
    )
    try:
        attestation_digest = verifier.verify(
            attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=replay_identity.digest,
            payload=unsigned_body,
            now=now,
        )
    except ValueError as exc:
        raise CaseExchangeV1Error(str(exc)) from exc

    exchange_identity = _address(
        raw.get("exchange_identity"),
        field_name="exchange_identity",
    )
    signed_body = dict(raw)
    signed_body.pop("exchange_identity", None)
    if exchange_identity != ContentAddress.for_value(signed_body):
        raise CaseExchangeV1Error("signed case exchange content-address mismatch")

    if replay_verification.manifest_identity != manifest.manifest_identity:
        raise CaseExchangeV1Error("replay manifest verification mismatch")

    return CaseExchangeVerificationV1(
        exchange_identity=exchange_identity,
        request_identity=request.request_identity,
        replay_manifest_identity=manifest.manifest_identity,
        replay_bundle_identity=replay_identity,
        attestation_digest=attestation_digest,
        source_authorization_identity=source_authorization.authorization_identity,
        recipient_authorization_identity=(
            recipient_authorization.authorization_identity
        ),
    )
