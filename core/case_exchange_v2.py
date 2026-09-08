"""XCH-02 portable authorization verification over Signed Case Exchange v1.

V2 deliberately wraps the complete signed XCH-01 envelope instead of introducing a
second exchange/signature authority. It carries only the exact authorization-policy
and minimal principal-context preimages needed to recompute the already signed
authorization receipts offline.

The wrapper is verification/transport only. It exposes no Canonical Case Ledger write,
restore, import, merge, epistemic-promotion or release authority.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from core.case_exchange_v1 import (
    CaseExchangeRequestV1,
    ExchangeAuthorizationV1,
    ExchangeParty,
    SignedCaseExchangeBundleV1,
    verify_signed_case_exchange,
)
from core.case_ledger.contracts import ContentAddress
from core.enterprise.authorization import AuthorizationEngine
from core.enterprise.authorization_policy import AuthorizationPolicyV1
from core.enterprise.contracts import AuthorizationContext, AttestationVerifier
from core.p3.contracts import canonical_json

CASE_EXCHANGE_V2_SCHEMA = "lukart.signed-case-exchange.v2"
PORTABLE_AUTH_CONTEXT_SCHEMA_V2 = "lukart.portable-authorization-context.v2"
PORTABLE_AUTH_PROOF_SCHEMA_V2 = "lukart.portable-authorization-proof.v2"
CASE_EXCHANGE_V2_SEMANTICS = "portable-authorization-reverification-only-no-import"

_CONTEXT_KEYS = frozenset(
    {"schema", "subject_id", "tenant_id", "roles", "case_ids", "workspace_ids"}
)
_PROOF_KEYS = frozenset({"schema", "party", "policy", "context", "proof_identity"})
_BUNDLE_KEYS = frozenset(
    {
        "schema",
        "semantics",
        "signed_exchange_v1",
        "source_authorization_proof",
        "recipient_authorization_proof",
        "exchange_identity",
    }
)


class CaseExchangeV2Error(ValueError):
    """Fail-closed XCH-02 portable exchange contract violation."""


def _copy_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise CaseExchangeV2Error(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise CaseExchangeV2Error(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise CaseExchangeV2Error(f"{field_name} must be an object")
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
    raise CaseExchangeV2Error(
        f"{field_name} key contract violation: " + "; ".join(details)
    )


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CaseExchangeV2Error(f"{field_name} must be nonblank and canonical")
    return value


def _text_list(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CaseExchangeV2Error(f"{field_name} must be a string list")
    items = tuple(cast(list[str], value))
    if any(not item or item != item.strip() for item in items):
        raise CaseExchangeV2Error(f"{field_name} contains a noncanonical value")
    return items


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise CaseExchangeV2Error(f"{field_name} must be a content-address object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise CaseExchangeV2Error(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class PortableAuthorizationContextV2:
    """Minimal context preimage; permissions are always re-derived from policy roles."""

    subject_id: str
    tenant_id: str
    roles: tuple[str, ...]
    case_ids: tuple[str, ...] = ()
    workspace_ids: tuple[str, ...] = ()
    schema: str = PORTABLE_AUTH_CONTEXT_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != PORTABLE_AUTH_CONTEXT_SCHEMA_V2:
            raise CaseExchangeV2Error(f"unsupported portable context schema: {self.schema}")
        subject_id = _text(self.subject_id, field_name="subject_id")
        tenant_id = _text(self.tenant_id, field_name="tenant_id")
        roles = tuple(sorted(set(self.roles)))
        case_ids = tuple(sorted(set(self.case_ids)))
        workspace_ids = tuple(sorted(set(self.workspace_ids)))
        if not roles or any(not item or item != item.strip() for item in roles):
            raise CaseExchangeV2Error("portable context requires canonical roles")
        if any(not item or item != item.strip() for item in case_ids):
            raise CaseExchangeV2Error("portable context case_ids are invalid")
        if any(not item or item != item.strip() for item in workspace_ids):
            raise CaseExchangeV2Error("portable context workspace_ids are invalid")
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "case_ids", case_ids)
        object.__setattr__(self, "workspace_ids", workspace_ids)

    @classmethod
    def from_context(cls, context: AuthorizationContext) -> PortableAuthorizationContextV2:
        return cls(
            subject_id=context.subject_id,
            tenant_id=context.tenant_id,
            roles=context.roles,
            case_ids=context.case_ids,
            workspace_ids=context.workspace_ids,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PortableAuthorizationContextV2:
        raw = _copy_mapping(value, field_name="portable authorization context")
        _require_exact_keys(
            raw,
            expected=_CONTEXT_KEYS,
            field_name="portable authorization context",
        )
        candidate = cls(
            subject_id=_text(raw.get("subject_id"), field_name="subject_id"),
            tenant_id=_text(raw.get("tenant_id"), field_name="tenant_id"),
            roles=_text_list(raw.get("roles"), field_name="roles"),
            case_ids=_text_list(raw.get("case_ids"), field_name="case_ids"),
            workspace_ids=_text_list(
                raw.get("workspace_ids"), field_name="workspace_ids"
            ),
            schema=_text(raw.get("schema"), field_name="context schema"),
        )
        if candidate.canonical_dict() != raw:
            raise CaseExchangeV2Error("portable authorization context is non-canonical")
        return candidate

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "subject_id": self.subject_id,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "case_ids": list(self.case_ids),
            "workspace_ids": list(self.workspace_ids),
        }

    def rebuild(self, policy: AuthorizationPolicyV1) -> AuthorizationContext:
        engine = AuthorizationEngine.from_policy(policy)
        return engine.build_context(
            subject_id=self.subject_id,
            tenant_id=self.tenant_id,
            roles=self.roles,
            case_ids=self.case_ids,
            workspace_ids=self.workspace_ids,
        )


@dataclass(frozen=True, slots=True)
class PortableAuthorizationProofV2:
    party: ExchangeParty
    policy: AuthorizationPolicyV1
    context: PortableAuthorizationContextV2
    proof_identity: ContentAddress
    schema: str = PORTABLE_AUTH_PROOF_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != PORTABLE_AUTH_PROOF_SCHEMA_V2:
            raise CaseExchangeV2Error(f"unsupported portable proof schema: {self.schema}")
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        party: ExchangeParty,
        authorization: ExchangeAuthorizationV1,
        request: CaseExchangeRequestV1,
        policy: AuthorizationPolicyV1,
        context: AuthorizationContext,
    ) -> PortableAuthorizationProofV2:
        portable_context = PortableAuthorizationContextV2.from_context(context)
        body = cls._body(party=party, policy=policy, context=portable_context)
        proof = cls(
            party=party,
            policy=policy,
            context=portable_context,
            proof_identity=ContentAddress.for_value(body),
        )
        proof.verify_for_authorization(authorization=authorization, request=request)
        return proof

    @staticmethod
    def _body(
        *,
        party: ExchangeParty,
        policy: AuthorizationPolicyV1,
        context: PortableAuthorizationContextV2,
    ) -> dict[str, object]:
        return {
            "schema": PORTABLE_AUTH_PROOF_SCHEMA_V2,
            "party": party.value,
            "policy": policy.canonical_dict(),
            "context": context.canonical_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PortableAuthorizationProofV2:
        raw = _copy_mapping(value, field_name="portable authorization proof")
        _require_exact_keys(raw, expected=_PROOF_KEYS, field_name="portable authorization proof")
        policy_raw = raw.get("policy")
        context_raw = raw.get("context")
        if not isinstance(policy_raw, Mapping) or not isinstance(context_raw, Mapping):
            raise CaseExchangeV2Error("portable authorization proof contains malformed objects")
        try:
            party = ExchangeParty(_text(raw.get("party"), field_name="proof party"))
            policy = AuthorizationPolicyV1.from_dict(cast(Mapping[str, object], policy_raw))
        except ValueError as exc:
            raise CaseExchangeV2Error(str(exc)) from exc
        candidate = cls(
            party=party,
            policy=policy,
            context=PortableAuthorizationContextV2.from_dict(
                cast(Mapping[str, object], context_raw)
            ),
            proof_identity=_address(raw.get("proof_identity"), field_name="proof_identity"),
            schema=_text(raw.get("schema"), field_name="proof schema"),
        )
        if candidate.canonical_dict() != raw:
            raise CaseExchangeV2Error("portable authorization proof is non-canonical")
        return candidate

    def canonical_body(self) -> dict[str, object]:
        return self._body(party=self.party, policy=self.policy, context=self.context)

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "proof_identity": self.proof_identity.canonical_dict(),
        }

    def verify_identity(self) -> None:
        try:
            self.policy.verify()
        except ValueError as exc:
            raise CaseExchangeV2Error(str(exc)) from exc
        if self.proof_identity != ContentAddress.for_value(self.canonical_body()):
            raise CaseExchangeV2Error("portable authorization proof content-address mismatch")

    def verify_for_authorization(
        self,
        *,
        authorization: ExchangeAuthorizationV1,
        request: CaseExchangeRequestV1,
    ) -> AuthorizationContext:
        self.verify_identity()
        authorization.verify_for_request(request)
        if authorization.party is not self.party:
            raise CaseExchangeV2Error("portable authorization party mismatch")
        if authorization.policy_digest != self.policy.policy_digest:
            raise CaseExchangeV2Error("portable authorization policy digest mismatch")
        if authorization.subject_id != self.context.subject_id:
            raise CaseExchangeV2Error("portable authorization subject mismatch")
        try:
            rebuilt = self.context.rebuild(self.policy)
        except ValueError as exc:
            raise CaseExchangeV2Error(str(exc)) from exc
        if rebuilt.digest() != authorization.context_digest:
            raise CaseExchangeV2Error("portable authorization context digest mismatch")

        engine = AuthorizationEngine.from_policy(self.policy)
        decision = engine.decide(
            rebuilt,
            authorization.permission,
            authorization.resource(),
            request_digest=authorization.request_digest,
            strict_scope=True,
        )
        if not decision.allowed:
            raise CaseExchangeV2Error("portable authorization recomputation denied")
        if decision.digest() != authorization.decision_digest:
            raise CaseExchangeV2Error("portable authorization decision recomputation mismatch")
        return rebuilt


@dataclass(frozen=True, slots=True)
class CaseExchangeVerificationV2:
    exchange_identity: ContentAddress
    signed_exchange_v1_identity: ContentAddress
    replay_bundle_identity: ContentAddress
    source_policy_digest: str
    recipient_policy_digest: str
    source_context_digest: str
    recipient_context_digest: str


@dataclass(frozen=True, slots=True)
class SignedCaseExchangeBundleV2:
    signed_exchange_v1: Mapping[str, object]
    source_authorization_proof: PortableAuthorizationProofV2
    recipient_authorization_proof: PortableAuthorizationProofV2
    exchange_identity: ContentAddress
    semantics: str = CASE_EXCHANGE_V2_SEMANTICS
    schema: str = CASE_EXCHANGE_V2_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CASE_EXCHANGE_V2_SCHEMA:
            raise CaseExchangeV2Error(f"unsupported signed case exchange v2 schema: {self.schema}")
        if self.semantics != CASE_EXCHANGE_V2_SEMANTICS:
            raise CaseExchangeV2Error("unknown signed case exchange v2 semantics")
        object.__setattr__(
            self,
            "signed_exchange_v1",
            _copy_mapping(self.signed_exchange_v1, field_name="signed exchange v1"),
        )
        self.verify_identity()

    @classmethod
    def build(
        cls,
        *,
        signed_exchange_v1: SignedCaseExchangeBundleV1,
        source_policy: AuthorizationPolicyV1,
        source_context: AuthorizationContext,
        recipient_policy: AuthorizationPolicyV1,
        recipient_context: AuthorizationContext,
    ) -> SignedCaseExchangeBundleV2:
        request = signed_exchange_v1.request
        source_proof = PortableAuthorizationProofV2.build(
            party=ExchangeParty.SOURCE,
            authorization=signed_exchange_v1.source_authorization,
            request=request,
            policy=source_policy,
            context=source_context,
        )
        recipient_proof = PortableAuthorizationProofV2.build(
            party=ExchangeParty.RECIPIENT,
            authorization=signed_exchange_v1.recipient_authorization,
            request=request,
            policy=recipient_policy,
            context=recipient_context,
        )
        signed_v1 = _copy_mapping(
            signed_exchange_v1.canonical_dict(), field_name="signed exchange v1"
        )
        body = cls._body(
            signed_exchange_v1=signed_v1,
            source_authorization_proof=source_proof,
            recipient_authorization_proof=recipient_proof,
        )
        return cls(
            signed_exchange_v1=signed_v1,
            source_authorization_proof=source_proof,
            recipient_authorization_proof=recipient_proof,
            exchange_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        signed_exchange_v1: Mapping[str, object],
        source_authorization_proof: PortableAuthorizationProofV2,
        recipient_authorization_proof: PortableAuthorizationProofV2,
    ) -> dict[str, object]:
        return {
            "schema": CASE_EXCHANGE_V2_SCHEMA,
            "semantics": CASE_EXCHANGE_V2_SEMANTICS,
            "signed_exchange_v1": dict(signed_exchange_v1),
            "source_authorization_proof": source_authorization_proof.canonical_dict(),
            "recipient_authorization_proof": recipient_authorization_proof.canonical_dict(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            signed_exchange_v1=self.signed_exchange_v1,
            source_authorization_proof=self.source_authorization_proof,
            recipient_authorization_proof=self.recipient_authorization_proof,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "exchange_identity": self.exchange_identity.canonical_dict(),
        }

    def verify_identity(self) -> None:
        if self.exchange_identity != ContentAddress.for_value(self.canonical_body()):
            raise CaseExchangeV2Error("signed case exchange v2 content-address mismatch")

    def verify(
        self,
        *,
        verifier: AttestationVerifier,
        now: int,
    ) -> CaseExchangeVerificationV2:
        return verify_signed_case_exchange_v2(
            self.canonical_dict(), verifier=verifier, now=now
        )


def verify_signed_case_exchange_v2(
    value: Mapping[str, object],
    *,
    verifier: AttestationVerifier,
    now: int,
) -> CaseExchangeVerificationV2:
    """Offline-verify XCH-01 plus exact historical authorization policy/context preimages."""

    raw = _copy_mapping(value, field_name="signed case exchange v2")
    _require_exact_keys(raw, expected=_BUNDLE_KEYS, field_name="signed case exchange v2")
    if raw.get("schema") != CASE_EXCHANGE_V2_SCHEMA:
        raise CaseExchangeV2Error(f"unsupported signed case exchange v2 schema: {raw.get('schema')}")
    if raw.get("semantics") != CASE_EXCHANGE_V2_SEMANTICS:
        raise CaseExchangeV2Error("unknown signed case exchange v2 semantics")

    signed_v1_raw = raw.get("signed_exchange_v1")
    source_proof_raw = raw.get("source_authorization_proof")
    recipient_proof_raw = raw.get("recipient_authorization_proof")
    if not all(
        isinstance(item, Mapping)
        for item in (signed_v1_raw, source_proof_raw, recipient_proof_raw)
    ):
        raise CaseExchangeV2Error("signed case exchange v2 contains malformed objects")

    signed_v1 = cast(Mapping[str, object], signed_v1_raw)
    try:
        v1_verification = verify_signed_case_exchange(signed_v1, verifier=verifier, now=now)
        request_raw = signed_v1.get("request")
        source_raw = signed_v1.get("source_authorization")
        recipient_raw = signed_v1.get("recipient_authorization")
        if not all(isinstance(item, Mapping) for item in (request_raw, source_raw, recipient_raw)):
            raise CaseExchangeV2Error("signed exchange v1 authorization objects are malformed")
        request = CaseExchangeRequestV1.from_dict(cast(Mapping[str, object], request_raw))
        source_authorization = ExchangeAuthorizationV1.from_dict(
            cast(Mapping[str, object], source_raw), request=request
        )
        recipient_authorization = ExchangeAuthorizationV1.from_dict(
            cast(Mapping[str, object], recipient_raw), request=request
        )
    except ValueError as exc:
        if isinstance(exc, CaseExchangeV2Error):
            raise
        raise CaseExchangeV2Error(str(exc)) from exc

    source_proof = PortableAuthorizationProofV2.from_dict(
        cast(Mapping[str, object], source_proof_raw)
    )
    recipient_proof = PortableAuthorizationProofV2.from_dict(
        cast(Mapping[str, object], recipient_proof_raw)
    )
    source_context = source_proof.verify_for_authorization(
        authorization=source_authorization, request=request
    )
    recipient_context = recipient_proof.verify_for_authorization(
        authorization=recipient_authorization, request=request
    )

    exchange_identity = _address(raw.get("exchange_identity"), field_name="exchange_identity")
    body = dict(raw)
    body.pop("exchange_identity", None)
    if exchange_identity != ContentAddress.for_value(body):
        raise CaseExchangeV2Error("signed case exchange v2 content-address mismatch")

    return CaseExchangeVerificationV2(
        exchange_identity=exchange_identity,
        signed_exchange_v1_identity=v1_verification.exchange_identity,
        replay_bundle_identity=v1_verification.replay_bundle_identity,
        source_policy_digest=source_proof.policy.policy_digest,
        recipient_policy_digest=recipient_proof.policy.policy_digest,
        source_context_digest=source_context.digest(),
        recipient_context_digest=recipient_context.digest(),
    )
