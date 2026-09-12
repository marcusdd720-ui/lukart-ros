"""Fail-closed governance for CIRP procedural rule packs.

This module does not create, discover, update, or certify law.  It verifies that
an already-constructed ``ProceduralRulePack`` is explicitly approved at its exact
content digest and remains fresh under an explicit versioned policy at the
caller's deterministic evaluation time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.cirp.contracts import (
    CIRPContractError,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
)
from core.p3.contracts import P3ContractError, content_digest, require_hex_digest

RULE_PACK_APPROVAL_SCHEMA_V1 = "lukart.cirp.rule-pack-approval.v1"
RULE_PACK_REGISTRY_SCHEMA_V1 = "lukart.cirp.rule-pack-registry.v1"
RULE_PACK_FRESHNESS_POLICY_SCHEMA_V1 = "lukart.cirp.rule-pack-freshness-policy.v1"
RULE_PACK_GOVERNANCE_RECEIPT_SCHEMA_V1 = "lukart.cirp.rule-pack-governance-receipt.v1"


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CIRPContractError(f"{field_name} cannot contain control characters")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except P3ContractError as exc:
        raise CIRPContractError(str(exc)) from exc


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CIRPContractError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class RulePackApproval:
    approval_id: str
    pack_id: str
    pack_digest: str
    verified_at: datetime
    approved_by: str
    revoked_at: datetime | None = None
    schema: str = RULE_PACK_APPROVAL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RULE_PACK_APPROVAL_SCHEMA_V1:
            raise CIRPContractError("unsupported rule-pack approval schema")
        for field_name in ("approval_id", "pack_id", "approved_by"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "pack_digest",
            _require_digest(self.pack_digest, field_name="pack_digest"),
        )
        _require_aware(self.verified_at, field_name="verified_at")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at, field_name="revoked_at")
            if self.revoked_at < self.verified_at:
                raise CIRPContractError("rule-pack revoked_at precedes verified_at")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "approval_id": self.approval_id,
            "pack_id": self.pack_id,
            "pack_digest": self.pack_digest,
            "verified_at": self.verified_at.isoformat(),
            "approved_by": self.approved_by,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class RulePackRegistry:
    registry_id: str
    version: str
    approvals: tuple[RulePackApproval, ...]
    schema: str = RULE_PACK_REGISTRY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RULE_PACK_REGISTRY_SCHEMA_V1:
            raise CIRPContractError("unsupported rule-pack registry schema")
        object.__setattr__(
            self,
            "registry_id",
            _require_nonblank(self.registry_id, field_name="registry_id"),
        )
        object.__setattr__(
            self,
            "version",
            _require_nonblank(self.version, field_name="registry version"),
        )
        keys = tuple((item.pack_id, item.pack_digest) for item in self.approvals)
        if len(keys) != len(set(keys)):
            raise CIRPContractError("rule-pack registry contains duplicate exact approvals")
        approval_ids = tuple(item.approval_id for item in self.approvals)
        if len(approval_ids) != len(set(approval_ids)):
            raise CIRPContractError("rule-pack registry contains duplicate approval_id values")
        object.__setattr__(
            self,
            "approvals",
            tuple(sorted(self.approvals, key=lambda item: (item.pack_id, item.pack_digest))),
        )

    def exact_approval(self, pack: ProceduralRulePack) -> RulePackApproval:
        digest = pack.digest()
        matches = tuple(
            item
            for item in self.approvals
            if item.pack_id == pack.pack_id and item.pack_digest == digest
        )
        if len(matches) != 1:
            raise CIRPContractError(
                "procedural rule pack lacks exactly one registry approval for its exact digest: "
                + pack.pack_id
            )
        return matches[0]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "registry_id": self.registry_id,
            "version": self.version,
            "approvals": [item.canonical_dict() for item in self.approvals],
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class RulePackFreshnessPolicy:
    policy_id: str
    version: str
    max_approval_age_days: int
    max_source_age_days: int
    require_verified_sources: bool = True
    schema: str = RULE_PACK_FRESHNESS_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RULE_PACK_FRESHNESS_POLICY_SCHEMA_V1:
            raise CIRPContractError("unsupported rule-pack freshness policy schema")
        object.__setattr__(
            self,
            "policy_id",
            _require_nonblank(self.policy_id, field_name="freshness policy_id"),
        )
        object.__setattr__(
            self,
            "version",
            _require_nonblank(self.version, field_name="freshness policy version"),
        )
        if self.max_approval_age_days < 0 or self.max_source_age_days < 0:
            raise CIRPContractError("freshness age limits cannot be negative")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "policy_id": self.policy_id,
            "version": self.version,
            "max_approval_age_days": self.max_approval_age_days,
            "max_source_age_days": self.max_source_age_days,
            "require_verified_sources": self.require_verified_sources,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class RulePackGovernanceReceipt:
    run_identity_digest: str
    request_digest: str
    rule_pack_set_digest: str
    registry_digest: str
    freshness_policy_digest: str
    evaluation_time: datetime
    approval_digests: tuple[str, ...]
    pack_digests: tuple[str, ...]
    schema: str = RULE_PACK_GOVERNANCE_RECEIPT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RULE_PACK_GOVERNANCE_RECEIPT_SCHEMA_V1:
            raise CIRPContractError("unsupported rule-pack governance receipt schema")
        for field_name in (
            "run_identity_digest",
            "request_digest",
            "rule_pack_set_digest",
            "registry_digest",
            "freshness_policy_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_digest(getattr(self, field_name), field_name=field_name),
            )
        _require_aware(self.evaluation_time, field_name="evaluation_time")
        for field_name in ("approval_digests", "pack_digests"):
            normalized = tuple(
                _require_digest(item, field_name=field_name)
                for item in getattr(self, field_name)
            )
            if not normalized:
                raise CIRPContractError(f"{field_name} cannot be empty")
            if len(normalized) != len(set(normalized)):
                raise CIRPContractError(f"{field_name} cannot contain duplicates")
            object.__setattr__(self, field_name, tuple(sorted(normalized)))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "run_identity_digest": self.run_identity_digest,
            "request_digest": self.request_digest,
            "rule_pack_set_digest": self.rule_pack_set_digest,
            "registry_digest": self.registry_digest,
            "freshness_policy_digest": self.freshness_policy_digest,
            "evaluation_time": self.evaluation_time.isoformat(),
            "approval_digests": list(self.approval_digests),
            "pack_digests": list(self.pack_digests),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def verify_rule_pack_governance(
    *,
    rule_packs: tuple[ProceduralRulePack, ...],
    registry: RulePackRegistry,
    freshness_policy: RulePackFreshnessPolicy,
    evaluation_time: datetime,
    run_identity_digest: str,
    request_digest: str,
    rule_pack_set_digest: str,
) -> RulePackGovernanceReceipt:
    """Verify approval and freshness independently from intrinsic pack validity."""

    _require_aware(evaluation_time, field_name="evaluation_time")
    _require_digest(run_identity_digest, field_name="run_identity_digest")
    _require_digest(request_digest, field_name="request_digest")
    _require_digest(rule_pack_set_digest, field_name="rule_pack_set_digest")
    if not rule_packs:
        raise CIRPContractError("rule-pack governance verification requires rule packs")

    approvals: list[RulePackApproval] = []
    pack_digests: list[str] = []
    approval_limit = timedelta(days=freshness_policy.max_approval_age_days)
    source_limit = timedelta(days=freshness_policy.max_source_age_days)

    for pack in rule_packs:
        pack_digest = pack.digest()
        approval = registry.exact_approval(pack)
        if approval.verified_at > evaluation_time:
            raise CIRPContractError(
                "rule-pack approval is future-dated relative to evaluation_time: " + pack.pack_id
            )
        if approval.revoked_at is not None and approval.revoked_at <= evaluation_time:
            raise CIRPContractError("rule-pack approval is revoked: " + pack.pack_id)
        if evaluation_time - approval.verified_at > approval_limit:
            raise CIRPContractError("rule-pack approval is stale: " + pack.pack_id)

        for source in pack.source_set:
            if source.retrieved_at > evaluation_time:
                raise CIRPContractError(
                    "rule-pack legal source retrieval is future-dated: " + source.source_id
                )
            if evaluation_time - source.retrieved_at > source_limit:
                raise CIRPContractError(
                    "rule-pack legal source freshness limit exceeded: " + source.source_id
                )
            if (
                freshness_policy.require_verified_sources
                and source.verification_status is not LegalSourceVerificationStatus.VERIFIED
            ):
                raise CIRPContractError(
                    "freshness policy requires VERIFIED legal sources: " + source.source_id
                )

        approvals.append(approval)
        pack_digests.append(pack_digest)

    return RulePackGovernanceReceipt(
        run_identity_digest=run_identity_digest,
        request_digest=request_digest,
        rule_pack_set_digest=rule_pack_set_digest,
        registry_digest=registry.digest(),
        freshness_policy_digest=freshness_policy.digest(),
        evaluation_time=evaluation_time,
        approval_digests=tuple(item.digest() for item in approvals),
        pack_digests=tuple(pack_digests),
    )
