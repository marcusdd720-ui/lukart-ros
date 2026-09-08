from __future__ import annotations

from copy import deepcopy

import pytest

from core.enterprise import (
    AUTHORIZATION_POLICY_SCHEMA_V1,
    AuthorizationEngine,
    AuthorizationPolicyV1,
    DataClassification,
    EnterpriseContractError,
    Permission,
    ResourceDescriptor,
    RoleDefinition,
)


def _roles() -> tuple[RoleDefinition, ...]:
    return (
        RoleDefinition(
            role="reviewer",
            permissions=(Permission.SECURITY_REVIEW, Permission.CASE_READ),
            max_classification=DataClassification.CONFIDENTIAL,
        ),
        RoleDefinition(
            role="operator",
            permissions=(Permission.TRUST_PROMOTE, Permission.CASE_READ),
            max_classification=DataClassification.INTERNAL,
        ),
    )


def test_policy_identity_is_deterministic_across_input_order() -> None:
    left = AuthorizationPolicyV1.build(_roles())
    right = AuthorizationPolicyV1.build(tuple(reversed(_roles())))

    assert left.policy_digest == right.policy_digest
    assert left.canonical_dict() == right.canonical_dict()
    assert left.schema == AUTHORIZATION_POLICY_SCHEMA_V1


def test_policy_identity_binds_role_and_enforcement_semantics() -> None:
    policy = AuthorizationPolicyV1.build(_roles())
    body = policy.canonical_body()

    assert body["enforcement"] == {
        "decision_semantics": "lukart.authorization-decision-semantics.v1",
        "deny_by_default": True,
        "tenant_scope": "exact-match.v1",
        "case_scope": "strict-or-bounded-context.v1",
        "workspace_scope": "strict-or-bounded-context.v1",
        "classification_order": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"],
        "trust_promotion_requires": "security:review",
    }

    changed = AuthorizationPolicyV1.build(
        (
            RoleDefinition(
                role="operator",
                permissions=(Permission.CASE_READ,),
                max_classification=DataClassification.INTERNAL,
            ),
            _roles()[0],
        )
    )
    assert changed.policy_digest != policy.policy_digest


def test_policy_snapshot_round_trip_reconstructs_exact_engine() -> None:
    engine = AuthorizationEngine(_roles())
    snapshot = engine.policy_snapshot()
    restored = AuthorizationPolicyV1.from_dict(snapshot.canonical_dict())
    replay_engine = AuthorizationEngine.from_policy(restored)

    context = replay_engine.build_context(
        subject_id="subject-1",
        tenant_id="tenant-a",
        roles=("operator",),
        case_ids=("case-1",),
    )
    resource = ResourceDescriptor(
        resource_id="resource-1",
        tenant_id="tenant-a",
        case_id="case-1",
        classification=DataClassification.INTERNAL,
    )
    decision = replay_engine.decide(context, Permission.CASE_READ, resource, strict_scope=True)

    assert decision.allowed is True
    assert decision.reason == "authorized"
    assert decision.policy_digest == engine.policy_digest()
    assert replay_engine.policy_snapshot().canonical_dict() == snapshot.canonical_dict()


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda value: value.__setitem__("unknown", True), "fields are invalid"),
        (
            lambda value: value.__setitem__("schema", "lukart.authorization-policy.v999"),
            "unsupported authorization policy schema",
        ),
        (lambda value: value.__setitem__("policy_digest", "0" * 64), "digest mismatch"),
        (
            lambda value: value["enforcement"].__setitem__("deny_by_default", False),
            "non-canonical",
        ),
        (
            lambda value: value["roles"][0]["permissions"].append("case:read"),
            "non-canonical",
        ),
        (
            lambda value: value["roles"][0].__setitem__("max_classification", "TOP_SECRET"),
            "enum value is invalid",
        ),
    ],
)
def test_policy_snapshot_tampering_and_unknowns_fail_closed(mutation, match: str) -> None:
    snapshot = deepcopy(AuthorizationPolicyV1.build(_roles()).canonical_dict())
    mutation(snapshot)

    with pytest.raises(EnterpriseContractError, match=match):
        AuthorizationPolicyV1.from_dict(snapshot)


def test_policy_change_is_explicit_and_changes_historical_decision_identity() -> None:
    historical = AuthorizationEngine(_roles())
    current = AuthorizationEngine(
        (
            RoleDefinition(
                role="operator",
                permissions=(Permission.TRUST_PROMOTE,),
                max_classification=DataClassification.INTERNAL,
            ),
            _roles()[0],
        )
    )
    resource = ResourceDescriptor(
        resource_id="resource-1",
        tenant_id="tenant-a",
        case_id=None,
        classification=DataClassification.INTERNAL,
    )
    historical_context = historical.build_context(
        subject_id="subject-1",
        tenant_id="tenant-a",
        roles=("operator",),
    )
    current_context = current.build_context(
        subject_id="subject-1",
        tenant_id="tenant-a",
        roles=("operator",),
    )

    historical_decision = historical.decide(
        historical_context,
        Permission.CASE_READ,
        resource,
    )
    current_decision = current.decide(current_context, Permission.CASE_READ, resource)

    assert historical_decision.allowed is True
    assert current_decision.allowed is False
    assert historical_decision.policy_digest != current_decision.policy_digest


def test_trust_promotion_still_requires_independent_security_review_permission() -> None:
    engine = AuthorizationEngine(_roles())
    resource = ResourceDescriptor(
        resource_id="trust-candidate",
        tenant_id="tenant-a",
        case_id=None,
        classification=DataClassification.INTERNAL,
    )
    operator = engine.build_context(
        subject_id="subject-1",
        tenant_id="tenant-a",
        roles=("operator",),
    )
    dual_role = engine.build_context(
        subject_id="subject-1",
        tenant_id="tenant-a",
        roles=("operator", "reviewer"),
    )

    denied = engine.decide(operator, Permission.TRUST_PROMOTE, resource)
    allowed = engine.decide(dual_role, Permission.TRUST_PROMOTE, resource)

    assert denied.allowed is False
    assert denied.reason == "trust promotion requires independent security-review permission"
    assert allowed.allowed is True
    assert denied.policy_digest == allowed.policy_digest == engine.policy_digest()
