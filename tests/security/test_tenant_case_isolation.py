"""Synthetic regression coverage for Enterprise tenant/case authorization isolation."""

import pytest

from core.enterprise.authorization import AuthorizationEngine, ResourceDescriptor
from core.enterprise.authorization_policy import RoleDefinition
from core.enterprise.contracts import (
    DataClassification,
    EnterpriseContractError,
    Permission,
)


def _engine() -> AuthorizationEngine:
    return AuthorizationEngine(
        (
            RoleDefinition(
                role="case-reader",
                permissions=(Permission.CASE_READ,),
                max_classification=DataClassification.CONFIDENTIAL,
            ),
        )
    )


def _resource(*, tenant_id: str, case_id: str) -> ResourceDescriptor:
    return ResourceDescriptor(
        resource_id=f"resource:{tenant_id}:{case_id}",
        tenant_id=tenant_id,
        case_id=case_id,
        classification=DataClassification.CONFIDENTIAL,
    )


def test_same_tenant_authorized_case_is_allowed() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="synthetic-user",
        tenant_id="tenant-a",
        roles=("case-reader",),
        case_ids=("case-a",),
    )

    decision = engine.decide(
        context,
        Permission.CASE_READ,
        _resource(tenant_id="tenant-a", case_id="case-a"),
    )

    assert decision.allowed is True
    assert decision.reason == "authorized"


def test_cross_tenant_resource_is_denied_before_other_scope_checks() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="synthetic-user",
        tenant_id="tenant-a",
        roles=("case-reader",),
        case_ids=("case-a",),
    )

    decision = engine.decide(
        context,
        Permission.CASE_READ,
        _resource(tenant_id="tenant-b", case_id="case-a"),
    )

    assert decision.allowed is False
    assert decision.reason == "cross-tenant access denied"


def test_same_tenant_cross_case_resource_is_denied() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="synthetic-user",
        tenant_id="tenant-a",
        roles=("case-reader",),
        case_ids=("case-a",),
    )

    decision = engine.decide(
        context,
        Permission.CASE_READ,
        _resource(tenant_id="tenant-a", case_id="case-b"),
    )

    assert decision.allowed is False
    assert decision.reason == "case scope denied"


def test_require_fails_closed_for_cross_tenant_access() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="synthetic-user",
        tenant_id="tenant-a",
        roles=("case-reader",),
        case_ids=("case-a",),
    )

    with pytest.raises(EnterpriseContractError, match="cross-tenant access denied"):
        engine.require(
            context,
            Permission.CASE_READ,
            _resource(tenant_id="tenant-b", case_id="case-a"),
        )
