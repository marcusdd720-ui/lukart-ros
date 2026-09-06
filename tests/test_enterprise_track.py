from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.enterprise import (
    ApiOperation,
    AttestationPurpose,
    AttestationSigner,
    AttestationVerifier,
    AuthorizationEngine,
    ControlEvidence,
    DataClassification,
    EnterpriseApiGuard,
    EnterpriseCertificationGate,
    EnterpriseContractError,
    EnterpriseGateState,
    EnterpriseRequest,
    EnterpriseScalePlan,
    FailureClass,
    FailureEvidence,
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    Permission,
    ProcessIsolationExecutor,
    ProvenanceMaterial,
    RedactingTelemetrySink,
    ResilienceMatrix,
    ResourceDescriptor,
    RoleDefinition,
    SliDirection,
    SliObservation,
    SloEvaluator,
    SloPolicy,
    SlsaStyleProvenance,
    SQLiteProvenanceStore,
    Threat,
    ThreatModel,
    ThreatSeverity,
    TrustZone,
    audit_workflow_action_pins,
    build_cyclonedx_sbom,
)
from core.p3.contracts import content_digest

ROOT = Path(__file__).resolve().parents[1]
WORKER_MODULE = "core.enterprise._worker_fixture"


def _roles() -> tuple[RoleDefinition, ...]:
    return (
        RoleDefinition(
            role="analyst",
            permissions=(
                Permission.CASE_READ,
                Permission.CASE_WRITE,
                Permission.EVIDENCE_READ,
                Permission.RUN_AGENT,
            ),
            max_classification=DataClassification.CONFIDENTIAL,
        ),
        RoleDefinition(
            role="security-reviewer",
            permissions=(
                Permission.CASE_READ,
                Permission.TRUST_PROMOTE,
                Permission.SECURITY_REVIEW,
            ),
            max_classification=DataClassification.RESTRICTED,
        ),
    )


def _resource(tenant: str = "tenant-a") -> ResourceDescriptor:
    return ResourceDescriptor(
        resource_id="case-1",
        tenant_id=tenant,
        case_id="case-1",
        classification=DataClassification.CONFIDENTIAL,
    )


def test_e0_governance_targets_enterprise_and_preserves_v1_baseline() -> None:
    policy = json.loads(
        (ROOT / "config" / "enterprise_v1.json").read_text(encoding="utf-8")
    )
    master = (ROOT / "MASTER_PLAN.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release = (
        ROOT / ".github" / "workflows" / "mvros-v1-release.yml"
    ).read_text(encoding="utf-8")

    assert policy["baseline"]["v1_0_1_immutable"] is True
    assert policy["baseline"]["locked_gold_mutation_for_pass"] is False
    assert "Roadmap target: `Enterprise Track E0-E10`" in master
    assert 'version = "1.1.0.dev0"' in pyproject
    assert "Development build — no release mutation" in release
    assert "Refusing to move an existing release tag" in release


def test_e1_threat_model_fails_closed_and_requires_zone_coverage() -> None:
    with pytest.raises(EnterpriseContractError):
        Threat(
            threat_id="T-CRITICAL",
            source_zone=TrustZone.EXTERNAL,
            target_zone=TrustZone.PRODUCT_CORE,
            asset="trusted fact",
            attack="inject trusted state",
            severity=ThreatSeverity.CRITICAL,
            mitigations=(),
            evidence_ids=(),
        )

    model = ThreatModel(
        (
            Threat(
                threat_id="T-API",
                source_zone=TrustZone.EXTERNAL,
                target_zone=TrustZone.API_EDGE,
                asset="API trust",
                attack="forge trusted state",
                severity=ThreatSeverity.CRITICAL,
                mitigations=("signed attestation", "authorization"),
                evidence_ids=("E3-attestation-tests", "E8-api-tests"),
            ),
            Threat(
                threat_id="T-WORKER",
                source_zone=TrustZone.UNTRUSTED_WORKER,
                target_zone=TrustZone.PRODUCT_CORE,
                asset="reasoning core",
                attack="worker bypass",
                severity=ThreatSeverity.HIGH,
                mitigations=("process boundary", "normal product validation"),
                evidence_ids=("E2-process-tests",),
            ),
        )
    )
    with pytest.raises(EnterpriseContractError, match="coverage missing"):
        model.require_zone_coverage((TrustZone.EXTERNAL, TrustZone.GOVERNANCE))
    assert len(model.digest()) == 64


def test_e2_process_isolation_sanitizes_environment_and_denies_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUKART_TEST_SECRET", "must-not-cross-worker-boundary")
    policy = IsolationPolicy(
        timeout_seconds=3.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=(
            f"{WORKER_MODULE}:environment_snapshot",
            f"{WORKER_MODULE}:network_probe",
        ),
    )
    executor = ProcessIsolationExecutor(policy)
    secret = executor.run(
        IsolatedTask(
            module=WORKER_MODULE,
            function="environment_snapshot",
            payload={"key": "LUKART_TEST_SECRET"},
        )
    )
    assert secret.output["value"] is None
    assert secret.controls.separate_process is True
    assert secret.controls.kernel_sandbox is False

    network = executor.run(
        IsolatedTask(module=WORKER_MODULE, function="network_probe", payload={})
    )
    assert network.output["network"] == "denied"
    assert network.controls.network_control == "python-runtime-guard"


def test_e2_hard_timeout_terminates_worker() -> None:
    policy = IsolationPolicy(
        timeout_seconds=0.15,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=(f"{WORKER_MODULE}:delayed",),
    )
    with pytest.raises(IsolatedExecutionError, match="hard timeout"):
        ProcessIsolationExecutor(policy).run(
            IsolatedTask(
                module=WORKER_MODULE,
                function="delayed",
                payload={"seconds": 1.0},
            )
        )


def test_e3_ed25519_attestation_rejects_tamper_expiry_and_revocation() -> None:
    signer = AttestationSigner.generate("release-key-1")
    payload = {"result": "PASS", "scope": "synthetic"}
    subject = content_digest({"artifact": "bundle"})
    attestation = signer.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest=subject,
        payload=payload,
        issued_at=100,
        expires_at=200,
        nonce="n-1",
    )
    verifier = AttestationVerifier({"release-key-1": signer.public_key_bytes()})
    assert verifier.verify(
        attestation,
        expected_purpose=AttestationPurpose.PROVENANCE,
        expected_subject_digest=subject,
        payload=payload,
        now=150,
    ) == attestation.digest()

    with pytest.raises(EnterpriseContractError, match="payload mismatch"):
        verifier.verify(
            attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=subject,
            payload={"result": "FAIL"},
            now=150,
        )
    with pytest.raises(EnterpriseContractError, match="expired"):
        verifier.verify(
            attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=subject,
            payload=payload,
            now=200,
        )
    revoked = AttestationVerifier(
        {"release-key-1": signer.public_key_bytes()},
        revoked_key_ids=("release-key-1",),
    )
    with pytest.raises(EnterpriseContractError, match="revoked"):
        revoked.verify(
            attestation,
            expected_purpose=AttestationPurpose.PROVENANCE,
            expected_subject_digest=subject,
            payload=payload,
            now=150,
        )


def test_e4_sbom_slsa_style_provenance_and_full_sha_workflows() -> None:
    bom = build_cyclonedx_sbom(ROOT / "pyproject.toml")
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.7"
    assert isinstance(bom["components"], list)
    assert bom["components"]

    material = ProvenanceMaterial(
        uri="git+https://github.com/marcusdd720-ui/lukart-ros",
        digest="b" * 64,
    )
    provenance = SlsaStyleProvenance(
        subject_name="lukart-enterprise-evidence",
        subject_digest=content_digest(bom),
        source_sha="a" * 40,
        builder_id="https://github.com/marcusdd720-ui/lukart-ros/actions",
        build_type="https://lukart.local/build/enterprise-gate/v1",
        materials=(material,),
        parameters={"profile": "enterprise"},
    )
    assert provenance.predicate()["predicateType"] == "https://slsa.dev/provenance/v1"
    assert len(provenance.digest()) == 64

    pin_report = audit_workflow_action_pins(ROOT)
    assert pin_report.scanned_files > 0
    assert pin_report.external_action_references > 0
    assert pin_report.findings == ()


def test_e4_pin_audit_rejects_movable_tag(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "bad.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    report = audit_workflow_action_pins(tmp_path)
    assert report.passed is False
    assert "full 40-character commit SHA" in report.findings[0].reason


def test_e5_authorization_denies_cross_tenant_and_separates_promotion() -> None:
    engine = AuthorizationEngine(_roles())
    analyst = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-1",),
    )
    assert engine.require(analyst, Permission.CASE_READ, _resource()).allowed is True
    with pytest.raises(EnterpriseContractError, match="cross-tenant"):
        engine.require(analyst, Permission.CASE_READ, _resource("tenant-b"))
    with pytest.raises(EnterpriseContractError, match="permission denied"):
        engine.require(analyst, Permission.TRUST_PROMOTE, _resource())

    reviewer = engine.build_context(
        subject_id="reviewer-1",
        tenant_id="tenant-a",
        roles=("security-reviewer",),
        case_ids=("case-1",),
    )
    assert engine.require(reviewer, Permission.TRUST_PROMOTE, _resource()).allowed is True


def test_e6_hash_chain_backup_restore_and_corruption_detection(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    with SQLiteProvenanceStore(path) as store:
        first = store.append(
            stream_id="case-1",
            event_type="evidence",
            payload={"id": "EV-1"},
        )
        second = store.append(
            stream_id="case-1",
            event_type="reasoning",
            payload={"decision": "ABSTAIN"},
        )
        assert second.previous_digest == first.record_digest
        source_head = store.head_digest()
        snapshot = tmp_path / "snapshot.db"
        assert store.backup_to(snapshot) == source_head

    restored_path = tmp_path / "restored.db"
    restored = SQLiteProvenanceStore.restore_verified(snapshot, restored_path)
    try:
        assert restored.head_digest() == source_head
    finally:
        restored.close()

    connection = sqlite3.connect(restored_path)
    try:
        connection.execute(
            "UPDATE provenance SET payload_json = ? WHERE sequence = 0",
            ('{"id":"EV-X"}',),
        )
        connection.commit()
    finally:
        connection.close()
    with SQLiteProvenanceStore(restored_path) as corrupted:
        with pytest.raises(EnterpriseContractError, match="payload digest mismatch"):
            corrupted.verify()


def test_e7_observability_redacts_sensitive_values_and_missing_sli_fails() -> None:
    email = "person" + "@" + "example.com"
    numeric_identifier = "1" * 11
    sink = RedactingTelemetrySink(max_attributes=8)
    event = sink.emit(
        "agent.result",
        {
            "email": email,
            "message": f"contact {email} ref {numeric_identifier}",
            "token": "synthetic-secret-token",
            "outcome": "ABSTAIN",
        },
        correlation_id="case-1/run-1",
    )
    assert event.attributes["email"] == "[REDACTED]"
    assert email not in event.attributes["message"]
    assert numeric_identifier not in event.attributes["message"]
    assert event.attributes["token"] == "[REDACTED]"
    assert event.attributes["outcome"] == "ABSTAIN"

    results = SloEvaluator().evaluate(
        (
            SloPolicy("error_rate", 0.01, SliDirection.LOWER_IS_BETTER),
            SloPolicy("availability", 0.99, SliDirection.HIGHER_IS_BETTER),
        ),
        (SliObservation("error_rate", 0.0),),
    )
    assert results[0].passed is True
    assert results[1].passed is False
    assert results[1].reason == "missing SLI evidence"


def test_e8_api_replay_idempotency_and_attested_trust_boundaries() -> None:
    engine = AuthorizationEngine(_roles())
    analyst = engine.build_context(
        subject_id="analyst-1",
        tenant_id="tenant-a",
        roles=("analyst",),
        case_ids=("case-1",),
    )
    guard = EnterpriseApiGuard(engine, rate_limit=10)
    request = EnterpriseRequest(
        request_id="req-1",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.MUTATE,
        permission=Permission.CASE_WRITE,
        payload={"action": "annotate"},
        nonce="nonce-1",
        idempotency_key="idem-1",
    )
    first = guard.process(request, analyst, _resource(), now=100)
    assert guard.process(request, analyst, _resource(), now=101) == first

    conflicting = EnterpriseRequest(
        request_id="req-2",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.MUTATE,
        permission=Permission.CASE_WRITE,
        payload={"action": "delete"},
        nonce="nonce-2",
        idempotency_key="idem-1",
    )
    with pytest.raises(EnterpriseContractError, match="idempotency key reused"):
        guard.process(conflicting, analyst, _resource(), now=102)

    read = EnterpriseRequest(
        request_id="req-read",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.READ,
        permission=Permission.CASE_READ,
        payload={},
        nonce="read-nonce",
    )
    guard.process(read, analyst, _resource(), now=103)
    with pytest.raises(EnterpriseContractError, match="replay nonce"):
        guard.process(read, analyst, _resource(), now=104)

    signer = AttestationSigner.generate("api-review-key")
    verifier = AttestationVerifier({"api-review-key": signer.public_key_bytes()})
    reviewer = engine.build_context(
        subject_id="reviewer-1",
        tenant_id="tenant-a",
        roles=("security-reviewer",),
        case_ids=("case-1",),
    )
    payload = {"candidate": "fact-1"}
    unsigned = EnterpriseRequest(
        request_id="req-trust",
        api_version="1.0.0",
        tenant_id="tenant-a",
        operation=ApiOperation.TRUST_PROMOTE,
        permission=Permission.TRUST_PROMOTE,
        payload=payload,
        nonce="trust-nonce",
        idempotency_key="trust-idem",
    )
    attestation = signer.sign(
        purpose=AttestationPurpose.API_TRUST,
        subject_digest=unsigned.digest(),
        payload=payload,
        issued_at=100,
        expires_at=200,
        nonce="attest-1",
    )
    signed = EnterpriseRequest(
        request_id=unsigned.request_id,
        api_version=unsigned.api_version,
        tenant_id=unsigned.tenant_id,
        operation=unsigned.operation,
        permission=unsigned.permission,
        payload=unsigned.payload,
        nonce=unsigned.nonce,
        idempotency_key=unsigned.idempotency_key,
        attestation=attestation,
    )
    trusted_guard = EnterpriseApiGuard(engine, verifier=verifier)
    receipt = trusted_guard.process(signed, reviewer, _resource(), now=150)
    assert receipt.attestation_digest == attestation.digest()


def test_e9_resilience_matrix_and_enterprise_scale_plan() -> None:
    required = tuple(FailureClass)
    evidence = tuple(
        FailureEvidence(
            failure_class=item,
            passed=True,
            integrity_digest=content_digest({"failure": item.value}),
            detail="synthetic adversarial control passed",
        )
        for item in required
    )
    matrix = ResilienceMatrix(evidence)
    matrix.require_coverage(required)
    assert matrix.passed is True
    assert len(matrix.digest()) == 64

    plan = EnterpriseScalePlan.default()
    assert plan.certification.evidence_count >= 10_000
    assert plan.certification.graph_nodes >= 10_000
    measurement = plan.run_fast()
    assert measurement.blast_radius_size == plan.fast.graph_nodes + 1
    assert len(measurement.work_digest) == 64


def test_e10_gate_cannot_self_claim_independent_review() -> None:
    gate = EnterpriseCertificationGate()
    incomplete = gate.evaluate(candidate_sha="a" * 40, evidence=())
    assert incomplete.state is EnterpriseGateState.INCOMPLETE
    assert incomplete.missing_stages == tuple(f"E{index}" for index in range(10))

    evidence = tuple(
        ControlEvidence(
            stage=f"E{index}",
            passed=True,
            evidence_digest=content_digest({"stage": index}),
            detail="automated engineering evidence",
        )
        for index in range(10)
    )
    result = gate.evaluate(candidate_sha="b" * 40, evidence=evidence)
    assert result.state is EnterpriseGateState.INDEPENDENT_REVIEW_REQUIRED
    assert result.independent_review_digest is None

    signer = AttestationSigner.generate("independent-review-key")
    verifier = AttestationVerifier({"independent-review-key": signer.public_key_bytes()})
    review_payload = {
        "reviewer_id": "external-reviewer-1",
        "scope": "E0-E10 security review",
    }
    attestation = signer.sign(
        purpose=AttestationPurpose.SECURITY_REVIEW,
        subject_digest=result.evidence_bundle_digest,
        payload=review_payload,
        issued_at=100,
        expires_at=200,
        nonce="review-1",
    )
    candidate = gate.apply_independent_review(
        result,
        review_payload=review_payload,
        review_attestation=attestation,
        verifier=verifier,
        now=150,
    )
    assert candidate.state is EnterpriseGateState.ENTERPRISE_CANDIDATE
    assert candidate.independent_review_digest == attestation.digest()


def test_e10_failed_control_blocks_candidate() -> None:
    evidence = [
        ControlEvidence(
            stage=f"E{index}",
            passed=index != 4,
            evidence_digest=content_digest({"stage": index}),
            detail="test evidence",
        )
        for index in range(10)
    ]
    result = EnterpriseCertificationGate().evaluate(
        candidate_sha="c" * 40,
        evidence=evidence,
    )
    assert result.state is EnterpriseGateState.FAIL
    assert result.failed_stages == ("E4",)
