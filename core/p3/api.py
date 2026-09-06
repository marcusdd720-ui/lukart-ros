"""P3-08 stable external API v1 built on the existing P2 digest envelope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.p2.runtime import ApiEnvelope, RuntimeContractError

from .contracts import P3ContractError, RuntimeIdentity, TrustLevel, content_digest


class ApiResourceKind(StrEnum):
    CASE = "case"
    EVIDENCE = "evidence"
    FACT = "fact"
    REASONING = "reasoning"
    RESULT = "result"
    REPLAY = "replay"
    KQM = "kqm"
    EXPLAINABILITY = "explainability"


@dataclass(frozen=True, slots=True)
class StableApiResource:
    kind: ApiResourceKind
    resource_id: str
    payload: Mapping[str, object]
    runtime_identity: RuntimeIdentity
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    api_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise P3ContractError("API resource_id is required")
        if self.trust_level is TrustLevel.TRUSTED and self.kind in {
            ApiResourceKind.FACT,
            ApiResourceKind.REASONING,
            ApiResourceKind.RESULT,
        }:
            # API transport may preserve a trusted state but can never create it.
            marker = self.payload.get("trusted_state_authorization")
            if not isinstance(marker, str) or not marker.strip():
                raise P3ContractError("trusted analytical API resource requires authorization marker")

    @property
    def schema(self) -> str:
        return f"lukart.api.{self.kind.value}.v1"

    def canonical_payload(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind.value,
            "trust_level": self.trust_level.value,
            "runtime_identity": self.runtime_identity.canonical_dict(),
            "runtime_identity_digest": self.runtime_identity.digest(),
            "payload": dict(self.payload),
            "payload_digest": content_digest(dict(self.payload)),
        }

    def to_envelope(self) -> ApiEnvelope:
        return ApiEnvelope.build(
            schema=self.schema,
            version=self.api_version,
            payload=self.canonical_payload(),
        )


class ApiContractRegistry:
    """Allow-list of exact schema/version pairs; unknown contracts fail closed."""

    def __init__(self) -> None:
        self._contracts: set[tuple[str, str]] = set()

    def register(self, *, schema: str, version: str) -> None:
        schema = schema.strip()
        version = version.strip()
        if not schema or not version:
            raise P3ContractError("API contract schema and version are required")
        key = (schema, version)
        if key in self._contracts:
            raise P3ContractError(f"duplicate API contract: {schema}@{version}")
        self._contracts.add(key)

    def register_v1_defaults(self) -> None:
        for kind in ApiResourceKind:
            self.register(schema=f"lukart.api.{kind.value}.v1", version="1.0.0")

    def decode(self, raw: str) -> ApiEnvelope:
        try:
            envelope = ApiEnvelope.from_json(raw)
        except RuntimeContractError as exc:
            raise P3ContractError(str(exc)) from exc
        if (envelope.schema, envelope.version) not in self._contracts:
            raise P3ContractError(
                f"unsupported API contract: {envelope.schema}@{envelope.version}"
            )
        identity = envelope.payload.get("runtime_identity")
        identity_digest = envelope.payload.get("runtime_identity_digest")
        payload = envelope.payload.get("payload")
        payload_digest = envelope.payload.get("payload_digest")
        if not isinstance(identity, dict) or not isinstance(identity_digest, str):
            raise P3ContractError("API runtime identity is missing")
        if content_digest(identity) != identity_digest:
            raise P3ContractError("API runtime identity digest mismatch")
        if not isinstance(payload, dict) or not isinstance(payload_digest, str):
            raise P3ContractError("API inner payload is missing")
        if content_digest(payload) != payload_digest:
            raise P3ContractError("API inner payload digest mismatch")
        return envelope
