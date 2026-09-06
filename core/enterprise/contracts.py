"""Enterprise trust, threat-model and cryptographic attestation contracts."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from core.p3.contracts import canonical_json, content_digest, require_hex_digest


class EnterpriseContractError(ValueError):
    """Fail-closed violation of an Enterprise boundary."""


class TrustZone(StrEnum):
    EXTERNAL = "EXTERNAL"
    API_EDGE = "API_EDGE"
    UNTRUSTED_WORKER = "UNTRUSTED_WORKER"
    PRODUCT_CORE = "PRODUCT_CORE"
    EVALUATION = "EVALUATION"
    GOVERNANCE = "GOVERNANCE"


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class Permission(StrEnum):
    CASE_READ = "case:read"
    CASE_WRITE = "case:write"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_WRITE = "evidence:write"
    RUN_AGENT = "agent:run"
    RUN_REPLAY = "replay:run"
    VIEW_KQM = "kqm:view"
    TRUST_PROMOTE = "trust:promote"
    RELEASE = "release:publish"
    SECURITY_REVIEW = "security:review"


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    subject_id: str
    tenant_id: str
    roles: tuple[str, ...]
    permissions: tuple[Permission, ...]
    case_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        subject = self.subject_id.strip()
        tenant = self.tenant_id.strip()
        if not subject or not tenant:
            raise EnterpriseContractError("subject_id and tenant_id are required")
        roles = tuple(sorted({item.strip() for item in self.roles}))
        if not roles or any(not item for item in roles):
            raise EnterpriseContractError("at least one nonblank role is required")
        permissions = tuple(sorted(set(self.permissions), key=lambda item: item.value))
        case_ids = tuple(sorted({item.strip() for item in self.case_ids}))
        if any(not item for item in case_ids):
            raise EnterpriseContractError("case_ids cannot contain blanks")
        object.__setattr__(self, "subject_id", subject)
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "permissions", permissions)
        object.__setattr__(self, "case_ids", case_ids)

    def require(
        self,
        permission: Permission,
        *,
        tenant_id: str,
        case_id: str | None = None,
    ) -> None:
        if tenant_id.strip() != self.tenant_id:
            raise EnterpriseContractError("cross-tenant access denied")
        if permission not in self.permissions:
            raise EnterpriseContractError(f"permission denied: {permission.value}")
        if case_id is not None and self.case_ids and case_id not in self.case_ids:
            raise EnterpriseContractError("case scope denied")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "permissions": [item.value for item in self.permissions],
            "case_ids": list(self.case_ids),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class ThreatSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class Threat:
    threat_id: str
    source_zone: TrustZone
    target_zone: TrustZone
    asset: str
    attack: str
    severity: ThreatSeverity
    mitigations: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        threat_id = self.threat_id.strip()
        asset = self.asset.strip()
        attack = self.attack.strip()
        mitigations = tuple(sorted({item.strip() for item in self.mitigations}))
        evidence = tuple(sorted({item.strip() for item in self.evidence_ids}))
        if not threat_id or not asset or not attack:
            raise EnterpriseContractError("threat id, asset and attack are required")
        if any(not item for item in mitigations + evidence):
            raise EnterpriseContractError("threat mitigations/evidence cannot be blank")
        if self.severity in {ThreatSeverity.HIGH, ThreatSeverity.CRITICAL}:
            if not mitigations or not evidence:
                raise EnterpriseContractError(
                    "high/critical threats require mitigations and evidence identifiers"
                )
        object.__setattr__(self, "threat_id", threat_id)
        object.__setattr__(self, "asset", asset)
        object.__setattr__(self, "attack", attack)
        object.__setattr__(self, "mitigations", mitigations)
        object.__setattr__(self, "evidence_ids", evidence)


class ThreatModel:
    def __init__(self, threats: Sequence[Threat]) -> None:
        ordered = tuple(sorted(threats, key=lambda item: item.threat_id))
        ids = [item.threat_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise EnterpriseContractError("duplicate threat_id")
        self._threats = ordered

    @property
    def threats(self) -> tuple[Threat, ...]:
        return self._threats

    def require_zone_coverage(self, zones: Sequence[TrustZone]) -> None:
        covered = {item.source_zone for item in self._threats} | {
            item.target_zone for item in self._threats
        }
        missing = sorted(set(zones) - covered, key=lambda item: item.value)
        if missing:
            values = ",".join(item.value for item in missing)
            raise EnterpriseContractError(f"threat-model zone coverage missing: {values}")

    def digest(self) -> str:
        payload = [
            {
                "threat_id": item.threat_id,
                "source_zone": item.source_zone.value,
                "target_zone": item.target_zone.value,
                "asset": item.asset,
                "attack": item.attack,
                "severity": item.severity.value,
                "mitigations": list(item.mitigations),
                "evidence_ids": list(item.evidence_ids),
            }
            for item in self._threats
        ]
        return content_digest(payload)


class AttestationPurpose(StrEnum):
    API_TRUST = "API_TRUST"
    PROVENANCE = "PROVENANCE"
    KQM = "KQM"
    RELEASE = "RELEASE"
    SECURITY_REVIEW = "SECURITY_REVIEW"


@dataclass(frozen=True, slots=True)
class SignedAttestation:
    key_id: str
    purpose: AttestationPurpose
    subject_digest: str
    payload_digest: str
    issued_at: int
    expires_at: int | None
    nonce: str
    signature_b64: str

    def canonical_body(self) -> dict[str, object]:
        return {
            "key_id": self.key_id,
            "purpose": self.purpose.value,
            "subject_digest": self.subject_digest,
            "payload_digest": self.payload_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }

    def digest(self) -> str:
        return content_digest({**self.canonical_body(), "signature_b64": self.signature_b64})


class AttestationSigner:
    """Ed25519 signer. Private key material is supplied at runtime, never from repository state."""

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        key_id = key_id.strip()
        if not key_id:
            raise EnterpriseContractError("key_id is required")
        self.key_id = key_id
        self._private_key = private_key

    @classmethod
    def generate(cls, key_id: str) -> AttestationSigner:
        return cls(key_id, Ed25519PrivateKey.generate())

    def public_key_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(
        self,
        *,
        purpose: AttestationPurpose,
        subject_digest: str,
        payload: Mapping[str, object],
        issued_at: int,
        expires_at: int | None = None,
        nonce: str,
    ) -> SignedAttestation:
        subject = require_hex_digest(subject_digest, field_name="subject_digest")
        if issued_at < 0:
            raise EnterpriseContractError("issued_at cannot be negative")
        if expires_at is not None and expires_at <= issued_at:
            raise EnterpriseContractError("expires_at must be after issued_at")
        nonce = nonce.strip()
        if not nonce:
            raise EnterpriseContractError("attestation nonce is required")
        body = {
            "key_id": self.key_id,
            "purpose": purpose.value,
            "subject_digest": subject,
            "payload_digest": content_digest(dict(payload)),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": nonce,
        }
        signature = self._private_key.sign(canonical_json(body).encode("utf-8"))
        return SignedAttestation(
            key_id=self.key_id,
            purpose=purpose,
            subject_digest=subject,
            payload_digest=str(body["payload_digest"]),
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
            signature_b64=base64.b64encode(signature).decode("ascii"),
        )


class AttestationVerifier:
    def __init__(self, public_keys: Mapping[str, bytes], revoked_key_ids: Sequence[str] = ()) -> None:
        self._keys: dict[str, Ed25519PublicKey] = {}
        for key_id, raw in public_keys.items():
            normalized = key_id.strip()
            if not normalized:
                raise EnterpriseContractError("public key id cannot be blank")
            self._keys[normalized] = Ed25519PublicKey.from_public_bytes(raw)
        self._revoked = frozenset(item.strip() for item in revoked_key_ids)
        if any(not item for item in self._revoked):
            raise EnterpriseContractError("revoked key ids cannot be blank")

    def verify(
        self,
        attestation: SignedAttestation,
        *,
        expected_purpose: AttestationPurpose,
        expected_subject_digest: str,
        payload: Mapping[str, object],
        now: int,
    ) -> str:
        expected_subject = require_hex_digest(
            expected_subject_digest,
            field_name="expected_subject_digest",
        )
        if attestation.key_id in self._revoked:
            raise EnterpriseContractError("attestation key is revoked")
        public_key = self._keys.get(attestation.key_id)
        if public_key is None:
            raise EnterpriseContractError("attestation key is not trusted")
        if attestation.purpose is not expected_purpose:
            raise EnterpriseContractError("attestation purpose mismatch")
        if attestation.subject_digest != expected_subject:
            raise EnterpriseContractError("attestation subject mismatch")
        if attestation.payload_digest != content_digest(dict(payload)):
            raise EnterpriseContractError("attestation payload mismatch")
        if now < attestation.issued_at:
            raise EnterpriseContractError("attestation is not yet valid")
        if attestation.expires_at is not None and now >= attestation.expires_at:
            raise EnterpriseContractError("attestation expired")
        try:
            signature = base64.b64decode(attestation.signature_b64, validate=True)
        except ValueError as exc:
            raise EnterpriseContractError("invalid attestation signature encoding") from exc
        try:
            public_key.verify(signature, canonical_json(attestation.canonical_body()).encode("utf-8"))
        except InvalidSignature as exc:
            raise EnterpriseContractError("attestation signature invalid") from exc
        return attestation.digest()
