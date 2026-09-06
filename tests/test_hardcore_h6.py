from __future__ import annotations

import pytest

from core.enterprise import (
    ApiOperation,
    AttestationPurpose,
    AttestationSigner,
    AttestationVerifier,
    AuthorizationEngine,
    DataClassification,
    EnterpriseApiGuard,
    EnterpriseContractError,
    EnterpriseRequest,
    Permission,
    ResourceDescriptor,
    RoleDefinition,
)


def _engine() -> AuthorizationEngine:
    return AuthorizationEngine(
        (
            RoleDefinition(
                "analyst",
                (Permission.CASE_READ, Permission.CASE_WRITE),
                DataClassification.CONFIDENTIAL,
            ),
            RoleDefinition(
                "reviewer",
                (
                    Permission.CASE_READ,
                    Permission.TRUST_PROMOTE,
                    Permission.SECURITY_REVIEW,
                ),
                DataClassification.RESTRICTED,
            ),
        )
    )


def _resource(
    *,
    tenant_id: str = "tenant-a",
    case_id: str = "case-a",
    workspace_id: str = "workspace-a",
) -> ResourceDescriptor:
    return ResourceDescriptor(
        resource_id=f"{case_id}/record-1",
        tenant_id=tenant_id,
        case_id=case_id,
        workspace_id=workspace_id,
        classification=DataClassification.CONFIDENTIAL,
    )


def _read_request(
    resource: ResourceDescriptor,
    *,
    nonce: str = "nonce-1",
) -> EnterpriseRequest:
    return EnterpriseRequest(
        request_id=f"request-{nonce}",
        api_version="1.1.0",
        tenant_id=resource.tenant_id,
        operation=ApiOperation.READ,
        permission=Permission.CASE_READ,
        payload={"read": True},
        nonce=nonce,
        resource_id=resource.resource_id,
        case_id=resource.case_id,
        workspace_id=resource.workspace_id,
    )


def test_h6_v11_receipt_binds_request_resource_context_and_policy() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    resource = _resource()
    request = _read_request(resource)
    receipt = EnterpriseApiGuard(engine).process(request, context, resource, now=100)
    assert receipt.accepted is True
    assert receipt.request_digest == request.digest()
    assert receipt.resource_digest == resource.digest()
    assert receipt.policy_digest == engine.policy_digest()
    assert len(receipt.authorization_digest) == 64
    assert len(receipt.digest()) == 64


def test_h6_confused_deputy_resource_binding_fails_closed() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    resource = _resource()
    request = EnterpriseRequest(
        request_id="request-confused",
        api_version="1.1.0",
        tenant_id="tenant-a",
        operation=ApiOperation.READ,
        permission=Permission.CASE_READ,
        payload={},
        nonce="nonce-confused",
        resource_id="case-b/record-1",
        case_id="case-b",
        workspace_id="workspace-a",
    )
    with pytest.raises(EnterpriseContractError, match="resource binding mismatch"):
        EnterpriseApiGuard(engine).process(request, context, resource, now=100)


def test_h6_cross_case_workspace_and_tenant_scopes_fail_closed() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    guard = EnterpriseApiGuard(engine)

    case_b = _resource(case_id="case-b")
    with pytest.raises(EnterpriseContractError, match="case scope denied"):
        guard.process(_read_request(case_b, nonce="case-b"), context, case_b, now=100)

    workspace_b = _resource(workspace_id="workspace-b")
    with pytest.raises(EnterpriseContractError, match="workspace scope denied"):
        guard.process(
            _read_request(workspace_b, nonce="workspace-b"),
            context,
            workspace_b,
            now=101,
        )

    tenant_b = _resource(tenant_id="tenant-b")
    with pytest.raises(EnterpriseContractError, match="tenant mismatch"):
        guard.process(_read_request(tenant_b, nonce="tenant-b"), context, tenant_b, now=102)


def test_h6_strict_scope_requires_explicit_case_and_workspace_membership() -> None:
    engine = _engine()
    unscoped = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
    )
    resource = _resource()
    with pytest.raises(EnterpriseContractError, match="case scope denied"):
        EnterpriseApiGuard(engine).process(
            _read_request(resource),
            unscoped,
            resource,
            now=100,
        )


def test_h6_replay_nonce_and_request_binding_are_deterministic() -> None:
    engine = _engine()
    context = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    resource = _resource()
    request = _read_request(resource)
    guard = EnterpriseApiGuard(engine)
    guard.process(request, context, resource, now=100)
    with pytest.raises(EnterpriseContractError, match="replay nonce"):
        guard.process(request, context, resource, now=101)

    left = engine.require(
        context,
        Permission.CASE_READ,
        resource,
        request_digest=request.digest(),
        strict_scope=True,
    )
    right = engine.require(
        context,
        Permission.CASE_READ,
        resource,
        request_digest=request.digest(),
        strict_scope=True,
    )
    assert left.digest() == right.digest()


def test_h6_trust_promotion_requires_v11_scope_review_permission_and_attestation() -> None:
    engine = _engine()
    resource = _resource()
    reviewer = engine.build_context(
        subject_id="reviewer-1",
        tenant_id="tenant-a",
        roles=("reviewer",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    legacy = EnterpriseRequest(
        request_id="legacy-promotion",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.TRUST_PROMOTE,
        permission=Permission.TRUST_PROMOTE,
        payload={"candidate": "F-1"},
        nonce="legacy-nonce",
        idempotency_key="legacy-idem",
    )
    with pytest.raises(EnterpriseContractError, match="requires API v1.1"):
        EnterpriseApiGuard(engine).process(legacy, reviewer, resource, now=100)

    unsigned = EnterpriseRequest(
        request_id="promotion-1",
        api_version="1.1.0",
        tenant_id="tenant-a",
        operation=ApiOperation.TRUST_PROMOTE,
        permission=Permission.TRUST_PROMOTE,
        payload={"candidate": "F-1"},
        nonce="promotion-nonce",
        idempotency_key="promotion-idem",
        resource_id=resource.resource_id,
        case_id=resource.case_id,
        workspace_id=resource.workspace_id,
    )
    signer = AttestationSigner.generate("h6-review-key")
    attestation = signer.sign(
        purpose=AttestationPurpose.API_TRUST,
        subject_digest=unsigned.digest(),
        payload=unsigned.payload,
        issued_at=90,
        expires_at=200,
        nonce="attestation-h6",
    )
    request = EnterpriseRequest(
        request_id=unsigned.request_id,
        api_version=unsigned.api_version,
        tenant_id=unsigned.tenant_id,
        operation=unsigned.operation,
        permission=unsigned.permission,
        payload=unsigned.payload,
        nonce=unsigned.nonce,
        idempotency_key=unsigned.idempotency_key,
        attestation=attestation,
        resource_id=unsigned.resource_id,
        case_id=unsigned.case_id,
        workspace_id=unsigned.workspace_id,
    )
    verifier = AttestationVerifier({"h6-review-key": signer.public_key_bytes()})
    receipt = EnterpriseApiGuard(engine, verifier=verifier).process(
        request,
        reviewer,
        resource,
        now=100,
    )
    assert receipt.accepted is True
    assert receipt.attestation_digest == attestation.digest()
