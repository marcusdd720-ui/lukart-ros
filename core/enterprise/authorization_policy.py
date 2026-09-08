"""POL-01 canonical authorization-policy identity and portable snapshot contract.

Authorization remains an Enterprise runtime decision boundary. This module only
makes the policy that drives that boundary explicit, deterministic and
content-addressed so historical decisions can be tied to exact policy semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.p3.contracts import content_digest

from .contracts import DataClassification, EnterpriseContractError, Permission

AUTHORIZATION_POLICY_SCHEMA_V1 = "lukart.authorization-policy.v1"
AUTHORIZATION_DECISION_SEMANTICS_V1 = "lukart.authorization-decision-semantics.v1"
AUTHORIZATION_SCOPE_SEMANTICS_V1 = "strict-or-bounded-context.v1"
AUTHORIZATION_TENANT_SEMANTICS_V1 = "exact-match.v1"
AUTHORIZATION_CLASSIFICATION_ORDER_V1 = (
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.RESTRICTED,
)


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    role: str
    permissions: tuple[Permission, ...]
    max_classification: DataClassification

    def __post_init__(self) -> None:
        role = self.role.strip()
        if not role:
            raise EnterpriseContractError("role name is required")
        if not isinstance(self.max_classification, DataClassification):
            raise EnterpriseContractError("role max_classification is invalid")
        if any(not isinstance(item, Permission) for item in self.permissions):
            raise EnterpriseContractError("role permissions contain an invalid permission")
        object.__setattr__(self, "role", role)
        object.__setattr__(
            self,
            "permissions",
            tuple(sorted(set(self.permissions), key=lambda item: item.value)),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "permissions": [item.value for item in self.permissions],
            "max_classification": self.max_classification.value,
        }


@dataclass(frozen=True, slots=True)
class AuthorizationPolicyV1:
    """Exact content-addressed policy used by ``AuthorizationEngine``.

    The snapshot binds both role data and enforcement semantics that affect an
    authorization decision. Unknown or non-canonical snapshots fail closed.
    """

    roles: tuple[RoleDefinition, ...]
    policy_digest: str
    schema: str = AUTHORIZATION_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AUTHORIZATION_POLICY_SCHEMA_V1:
            raise EnterpriseContractError(f"unsupported authorization policy schema: {self.schema}")
        ordered = tuple(sorted(self.roles, key=lambda item: item.role))
        names = tuple(item.role for item in ordered)
        if not ordered:
            raise EnterpriseContractError("authorization policy requires role definitions")
        if len(names) != len(set(names)):
            raise EnterpriseContractError("authorization policy contains duplicate roles")
        object.__setattr__(self, "roles", ordered)
        if not self.policy_digest or self.policy_digest != self.policy_digest.strip().lower():
            raise EnterpriseContractError("authorization policy digest must be canonical")
        self.verify()

    @classmethod
    def build(cls, roles: Sequence[RoleDefinition]) -> AuthorizationPolicyV1:
        ordered = tuple(sorted(roles, key=lambda item: item.role))
        names = tuple(item.role for item in ordered)
        if not ordered:
            raise EnterpriseContractError("authorization policy requires role definitions")
        if len(names) != len(set(names)):
            raise EnterpriseContractError("authorization policy contains duplicate roles")
        body = cls._body(ordered)
        return cls(roles=ordered, policy_digest=content_digest(body))

    @staticmethod
    def _body(roles: tuple[RoleDefinition, ...]) -> dict[str, object]:
        return {
            "schema": AUTHORIZATION_POLICY_SCHEMA_V1,
            "roles": [item.canonical_dict() for item in roles],
            "enforcement": {
                "decision_semantics": AUTHORIZATION_DECISION_SEMANTICS_V1,
                "deny_by_default": True,
                "tenant_scope": AUTHORIZATION_TENANT_SEMANTICS_V1,
                "case_scope": AUTHORIZATION_SCOPE_SEMANTICS_V1,
                "workspace_scope": AUTHORIZATION_SCOPE_SEMANTICS_V1,
                "classification_order": [
                    item.value for item in AUTHORIZATION_CLASSIFICATION_ORDER_V1
                ],
                "trust_promotion_requires": Permission.SECURITY_REVIEW.value,
            },
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(self.roles)

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "policy_digest": self.policy_digest}

    def verify(self) -> None:
        if self.policy_digest != content_digest(self.canonical_body()):
            raise EnterpriseContractError("authorization policy digest mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> AuthorizationPolicyV1:
        expected_keys = {"schema", "roles", "enforcement", "policy_digest"}
        if set(value) != expected_keys:
            raise EnterpriseContractError("authorization policy fields are invalid")
        if value.get("schema") != AUTHORIZATION_POLICY_SCHEMA_V1:
            raise EnterpriseContractError("unsupported authorization policy schema")
        raw_roles = value.get("roles")
        if not isinstance(raw_roles, list) or not raw_roles:
            raise EnterpriseContractError("authorization policy roles are invalid")

        roles: list[RoleDefinition] = []
        for raw_role in raw_roles:
            if not isinstance(raw_role, Mapping):
                raise EnterpriseContractError("authorization policy role is invalid")
            if set(raw_role) != {"role", "permissions", "max_classification"}:
                raise EnterpriseContractError("authorization policy role fields are invalid")
            role = raw_role.get("role")
            raw_permissions = raw_role.get("permissions")
            max_classification = raw_role.get("max_classification")
            if not isinstance(role, str) or not isinstance(raw_permissions, list):
                raise EnterpriseContractError("authorization policy role values are invalid")
            if not isinstance(max_classification, str) or any(
                not isinstance(item, str) for item in raw_permissions
            ):
                raise EnterpriseContractError("authorization policy role values are invalid")
            try:
                permissions = tuple(Permission(item) for item in raw_permissions)
                classification = DataClassification(max_classification)
            except ValueError as exc:
                raise EnterpriseContractError("authorization policy enum value is invalid") from exc
            roles.append(
                RoleDefinition(
                    role=role,
                    permissions=permissions,
                    max_classification=classification,
                )
            )

        digest = value.get("policy_digest")
        if not isinstance(digest, str):
            raise EnterpriseContractError("authorization policy digest is invalid")
        candidate = cls(roles=tuple(roles), policy_digest=digest)
        if candidate.canonical_dict() != dict(value):
            raise EnterpriseContractError("authorization policy snapshot is non-canonical")
        return candidate

    def classification_rank(self, classification: DataClassification) -> int:
        try:
            return AUTHORIZATION_CLASSIFICATION_ORDER_V1.index(classification)
        except ValueError as exc:
            raise EnterpriseContractError("unknown data classification") from exc
