from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from core.enterprise import (
    ApiOperation,
    AuthorizationEngine,
    DataClassification,
    EnterpriseApiGuard,
    EnterpriseContractError,
    EnterpriseRequest,
    Permission,
    ResourceDescriptor,
    RoleDefinition,
)
from core.p3 import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


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


def _request(resource: ResourceDescriptor, *, nonce: str) -> EnterpriseRequest:
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


def _expect_denial(action: Callable[[], object], marker: str) -> dict[str, object]:
    try:
        action()
    except EnterpriseContractError as exc:
        if marker not in str(exc):
            raise RuntimeError(f"unexpected H6 denial reason: {exc}") from exc
        return {"denied": True, "reason_class": marker}
    raise RuntimeError(f"H6 boundary unexpectedly accepted condition: {marker}")


def build_h6_evidence(candidate_sha: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if head != candidate:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    policy_document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    h6 = policy_document.get("h6_authorization_isolation")
    if not isinstance(h6, dict):
        raise RuntimeError("H6 authorization policy is missing")
    required = {
        "strict_api_version": "1.1.0",
        "tenant_scope": "DENY_UNDECLARED",
        "case_scope": "DENY_UNDECLARED",
        "workspace_scope": "DENY_UNDECLARED",
        "request_resource_binding_required": True,
        "nonce_replay_protection_required": True,
        "trust_promotion_requires_security_review": True,
        "legacy_trust_promotion": "DENY",
    }
    for key, expected in required.items():
        if h6.get(key) != expected:
            raise RuntimeError(f"H6 policy mismatch for {key}: {h6.get(key)!r} != {expected!r}")

    engine = _engine()
    context = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    resource = _resource()
    request = _request(resource, nonce="success")
    receipt = EnterpriseApiGuard(engine).process(request, context, resource, now=100)
    if receipt.resource_digest != resource.digest():
        raise RuntimeError("H6 receipt is not bound to resource identity")
    if receipt.policy_digest != engine.policy_digest():
        raise RuntimeError("H6 receipt is not bound to authorization policy")

    case_b = _resource(case_id="case-b")
    workspace_b = _resource(workspace_id="workspace-b")
    tenant_b = _resource(tenant_id="tenant-b")
    unscoped = engine.build_context(
        subject_id="analyst-unscoped",
        tenant_id="tenant-a",
        roles=("analyst",),
    )
    denials = {
        "cross_case": _expect_denial(
            lambda: EnterpriseApiGuard(engine).process(
                _request(case_b, nonce="case-b"), context, case_b, now=101
            ),
            "case scope denied",
        ),
        "cross_workspace": _expect_denial(
            lambda: EnterpriseApiGuard(engine).process(
                _request(workspace_b, nonce="workspace-b"),
                context,
                workspace_b,
                now=102,
            ),
            "workspace scope denied",
        ),
        "cross_tenant": _expect_denial(
            lambda: EnterpriseApiGuard(engine).process(
                _request(tenant_b, nonce="tenant-b"), context, tenant_b, now=103
            ),
            "tenant mismatch",
        ),
        "undeclared_scope": _expect_denial(
            lambda: EnterpriseApiGuard(engine).process(
                _request(resource, nonce="unscoped"), unscoped, resource, now=104
            ),
            "case scope denied",
        ),
    }

    confused = EnterpriseRequest(
        request_id="request-confused",
        api_version="1.1.0",
        tenant_id="tenant-a",
        operation=ApiOperation.READ,
        permission=Permission.CASE_READ,
        payload={},
        nonce="confused",
        resource_id="case-b/record-1",
        case_id="case-b",
        workspace_id="workspace-a",
    )
    denials["confused_deputy"] = _expect_denial(
        lambda: EnterpriseApiGuard(engine).process(confused, context, resource, now=105),
        "resource binding mismatch",
    )

    replay_guard = EnterpriseApiGuard(engine)
    replay_request = _request(resource, nonce="replay")
    replay_guard.process(replay_request, context, resource, now=106)
    denials["nonce_replay"] = _expect_denial(
        lambda: replay_guard.process(replay_request, context, resource, now=107),
        "replay nonce",
    )

    legacy_promotion = EnterpriseRequest(
        request_id="legacy-promotion",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.TRUST_PROMOTE,
        permission=Permission.TRUST_PROMOTE,
        payload={"candidate": "F-1"},
        nonce="legacy-promotion",
        idempotency_key="legacy-promotion",
    )
    reviewer = engine.build_context(
        subject_id="reviewer-1",
        tenant_id="tenant-a",
        roles=("reviewer",),
        case_ids=("case-a",),
        workspace_ids=("workspace-a",),
    )
    denials["legacy_promotion"] = _expect_denial(
        lambda: EnterpriseApiGuard(engine).process(
            legacy_promotion,
            reviewer,
            resource,
            now=108,
        ),
        "requires API v1.1",
    )

    decision = engine.require(
        context,
        Permission.CASE_READ,
        resource,
        request_digest=request.digest(),
        strict_scope=True,
    )
    evidence: dict[str, object] = {
        "schema": "lukart.hardcore.h6-authorization-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "policy_digest": content_digest(h6),
        "authorization_policy_digest": engine.policy_digest(),
        "request_digest": request.digest(),
        "resource_digest": resource.digest(),
        "authorization_decision_digest": decision.digest(),
        "receipt_digest": receipt.digest(),
        "adversarial_denials": denials,
        "state": "CONTROL_PASS",
    }
    evidence["evidence_digest"] = content_digest(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate H6 authorization isolation closure")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="build/hardcore/h6-authorization-isolation.json")
    args = parser.parse_args()
    evidence = build_h6_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H6_AUTHORIZATION_ISOLATION=PASS")
    print(f"H6_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H6_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H6_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
