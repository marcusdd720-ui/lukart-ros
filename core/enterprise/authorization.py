"""E5 identity, authorization and tenant/case data-isolation controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.p3.contracts import content_digest

from .contracts import (
    AuthorizationContext,
    DataClassification,
    EnterpriseContractError,
    Permission,
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
        object.__setattr__(self, "role", role)
        object.__setattr__(
            self,
            "permissions",
            tuple(sorted(set(self.permissions), key=lambda item: item.value)),
        )


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    resource_id: str
    tenant_id: str
    case_id: str | None
    classification: DataClassification

    def __post_init__(self) -> None:
        if not self.resource_id.strip() or not self.tenant_id.strip():
            raise EnterpriseContractError("resource_id and tenant_id are required")
        if self.case_id is not None and not self.case_id.strip():
            raise EnterpriseContractError("case_id cannot be blank")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    subject_id: str
    permission: Permission
    resource_id: str
    reason: str
    context_digest: str

    def digest(self) -> str:
        return content_digest(
            {
                "allowed": self.allowed,
                "subject_id": self.subject_id,
                "permission": self.permission.value,
                "resource_id": self.resource_id,
                "reason": self.reason,
                "context_digest": self.context_digest,
            }
        )


_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class AuthorizationEngine:
    def __init__(self, roles: Sequence[RoleDefinition]) -> None:
        definitions: dict[str, RoleDefinition] = {}
        for role in roles:
            if role.role in definitions:
                raise EnterpriseContractError(f"duplicate role definition: {role.role}")
            definitions[role.role] = role
        if not definitions:
            raise EnterpriseContractError("authorization engine requires role definitions")
        self._roles = definitions

    def build_context(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        roles: Sequence[str],
        case_ids: Sequence[str] = (),
    ) -> AuthorizationContext:
        normalized_roles = tuple(sorted({item.strip() for item in roles}))
        if not normalized_roles or any(not item for item in normalized_roles):
            raise EnterpriseContractError("principal roles are required")
        unknown = sorted(set(normalized_roles) - self._roles.keys())
        if unknown:
            raise EnterpriseContractError(f"unknown roles: {','.join(unknown)}")
        permissions = {
            permission
            for role in normalized_roles
            for permission in self._roles[role].permissions
        }
        return AuthorizationContext(
            subject_id=subject_id,
            tenant_id=tenant_id,
            roles=normalized_roles,
            permissions=tuple(permissions),
            case_ids=tuple(case_ids),
        )

    def _classification_allowed(
        self,
        context: AuthorizationContext,
        classification: DataClassification,
    ) -> bool:
        highest = max(
            (_CLASSIFICATION_RANK[self._roles[role].max_classification] for role in context.roles),
            default=-1,
        )
        return _CLASSIFICATION_RANK[classification] <= highest

    def decide(
        self,
        context: AuthorizationContext,
        permission: Permission,
        resource: ResourceDescriptor,
    ) -> AuthorizationDecision:
        allowed = False
        reason = "deny-by-default"
        if resource.tenant_id != context.tenant_id:
            reason = "cross-tenant access denied"
        elif permission not in context.permissions:
            reason = "permission denied"
        elif (
            resource.case_id is not None
            and context.case_ids
            and resource.case_id not in context.case_ids
        ):
            reason = "case scope denied"
        elif not self._classification_allowed(context, resource.classification):
            reason = "data classification exceeds role clearance"
        elif (
            permission is Permission.TRUST_PROMOTE
            and Permission.SECURITY_REVIEW not in context.permissions
        ):
            reason = "trust promotion requires independent security-review permission"
        else:
            allowed = True
            reason = "authorized"
        return AuthorizationDecision(
            allowed=allowed,
            subject_id=context.subject_id,
            permission=permission,
            resource_id=resource.resource_id,
            reason=reason,
            context_digest=context.digest(),
        )

    def require(
        self,
        context: AuthorizationContext,
        permission: Permission,
        resource: ResourceDescriptor,
    ) -> AuthorizationDecision:
        decision = self.decide(context, permission, resource)
        if not decision.allowed:
            raise EnterpriseContractError(decision.reason)
        return decision

    def policy_digest(self) -> str:
        policy: Mapping[str, object] = {
            role: {
                "permissions": [item.value for item in definition.permissions],
                "max_classification": definition.max_classification.value,
            }
            for role, definition in sorted(self._roles.items())
        }
        return content_digest(policy)
