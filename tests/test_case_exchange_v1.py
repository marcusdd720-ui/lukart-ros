from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.case_exchange_v1 as exchange_module
from core.case_exchange_v1 import (
    CASE_EXCHANGE_SEMANTICS_V1,
    CaseExchangeRequestV1,
    CaseExchangeV1Error,
    SignedCaseExchangeBundleV1,
    verify_signed_case_exchange,
)
from core.case_ledger import CanonicalCaseLedger, CaseId, ObjectId
from core.case_ledger.contracts import ContentAddress
from core.case_replay_v2 import CaseReplayBundleV2
from core.enterprise.authorization import (
    AuthorizationDecision,
    AuthorizationEngine,
    ResourceDescriptor,
    RoleDefinition,
)
from core.enterprise.contracts import (
    AttestationSigner,
    AttestationVerifier,
    DataClassification,
    Permission,
)
from core.p3.contracts import RuntimeIdentity, canonical_json
from core.p3.versioning import CaseMigrationRegistry
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicLedgerService, EpistemicPolicyV2
from knowledge.evidence_trust_graph import TrustPolicyV1


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=("e" * 64,),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest="f" * 64,
        python_implementation="CPython",
        python_version="3.13.7",
        platform_tag="linux-x86_64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _replay(tmp_path: Path) -> CaseReplayBundleV2:
    tmp_path.mkdir(parents=True, exist_ok=True)
    case_id = CaseId("CASE-XCH-001")
    with CanonicalCaseLedger(tmp_path / "xch.db") as ledger:
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-XCH-1"),
            assertion_type="claim.v1",
            content={"value": "portable"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        ledger_bundle = ledger.export_case(case_id)
    return CaseReplayBundleV2.build(
        ledger_bundle=ledger_bundle,
        runtime_identity=_runtime(),
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
    )


def _engine() -> AuthorizationEngine:
    return AuthorizationEngine(
        (
            RoleDefinition(
                role="source-reader",
                permissions=(Permission.CASE_READ,),
                max_classification=DataClassification.RESTRICTED,
            ),
            RoleDefinition(
                role="recipient-writer",
                permissions=(Permission.CASE_WRITE,),
                max_classification=DataClassification.RESTRICTED,
            ),
        )
    )


def _request(
    *,
    recipient_tenant: str = "tenant-b",
    recipient_case: str = "CASE-DEST-001",
) -> CaseExchangeRequestV1:
    return CaseExchangeRequestV1.build(
        source_tenant_id="tenant-a",
        source_case_id=CaseId("CASE-XCH-001"),
        recipient_tenant_id=recipient_tenant,
        recipient_case_id=CaseId(recipient_case),
    )


def _authorizations(
    request: CaseExchangeRequestV1,
) -> tuple[
    AuthorizationDecision,
    ResourceDescriptor,
    AuthorizationDecision,
    ResourceDescriptor,
]:
    engine = _engine()
    source_resource = ResourceDescriptor(
        resource_id="case-source",
        tenant_id=request.source_tenant_id,
        case_id=request.source_case_id.value,
        classification=DataClassification.CONFIDENTIAL,
    )
    recipient_resource = ResourceDescriptor(
        resource_id="case-recipient",
        tenant_id=request.recipient_tenant_id,
        case_id=request.recipient_case_id.value,
        classification=DataClassification.CONFIDENTIAL,
    )
    source_context = engine.build_context(
        subject_id="alice",
        tenant_id=request.source_tenant_id,
        roles=("source-reader",),
        case_ids=(request.source_case_id.value,),
    )
    recipient_context = engine.build_context(
        subject_id="bob",
        tenant_id=request.recipient_tenant_id,
        roles=("recipient-writer",),
        case_ids=(request.recipient_case_id.value,),
    )
    source_decision = engine.require(
        source_context,
        Permission.CASE_READ,
        source_resource,
        request_digest=request.request_identity.digest,
        strict_scope=True,
    )
    recipient_decision = engine.require(
        recipient_context,
        Permission.CASE_WRITE,
        recipient_resource,
        request_digest=request.request_identity.digest,
        strict_scope=True,
    )
    return (
        source_decision,
        source_resource,
        recipient_decision,
        recipient_resource,
    )


def _bundle(
    tmp_path: Path,
    *,
    request: CaseExchangeRequestV1 | None = None,
    signer: AttestationSigner | None = None,
    issued_at: int = 1_000,
    expires_at: int | None = 2_000,
    nonce: str = "nonce-1",
) -> tuple[SignedCaseExchangeBundleV1, AttestationSigner]:
    active_request = request or _request()
    source_decision, source_resource, recipient_decision, recipient_resource = (
        _authorizations(active_request)
    )
    active_signer = signer or AttestationSigner.generate("exchange-key-1")
    bundle = SignedCaseExchangeBundleV1.build(
        request=active_request,
        replay_bundle=_replay(tmp_path),
        source_decision=source_decision,
        source_resource=source_resource,
        recipient_decision=recipient_decision,
        recipient_resource=recipient_resource,
        signer=active_signer,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    return bundle, active_signer


def _serialized(bundle: SignedCaseExchangeBundleV1) -> dict[str, object]:
    decoded = json.loads(canonical_json(bundle.canonical_dict()))
    assert isinstance(decoded, dict)
    return decoded


def _rebind_exchange_identity(raw: dict[str, object]) -> None:
    body = dict(raw)
    body.pop("exchange_identity", None)
    raw["exchange_identity"] = ContentAddress.for_value(body).canonical_dict()


def test_signed_case_exchange_verifies_offline_and_binds_exact_replay(
    tmp_path: Path,
) -> None:
    bundle, signer = _bundle(tmp_path)
    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )

    result = bundle.verify(verifier=verifier, now=1_500)

    assert result.exchange_identity == bundle.exchange_identity
    assert result.request_identity == bundle.request.request_identity
    replay_identity = bundle.replay_bundle["bundle_identity"]
    assert isinstance(replay_identity, dict)
    assert result.replay_bundle_identity == ContentAddress.from_dict(replay_identity)
    assert result.replay_manifest_identity.digest
    assert result.attestation_digest == bundle.attestation.digest()


def test_identical_inputs_produce_identical_exchange_identity(
    tmp_path: Path,
) -> None:
    signer = AttestationSigner.generate("deterministic-key")
    request = _request()
    first, _ = _bundle(
        tmp_path / "first",
        request=request,
        signer=signer,
        nonce="same-nonce",
    )
    second, _ = _bundle(
        tmp_path / "second",
        request=request,
        signer=signer,
        nonce="same-nonce",
    )

    assert first.exchange_identity == second.exchange_identity
    assert first.attestation.signature_b64 == second.attestation.signature_b64


def test_recipient_scope_changes_exchange_identity(tmp_path: Path) -> None:
    signer = AttestationSigner.generate("recipient-key")
    first, _ = _bundle(
        tmp_path / "first",
        request=_request(recipient_tenant="tenant-b"),
        signer=signer,
    )
    second, _ = _bundle(
        tmp_path / "second",
        request=_request(recipient_tenant="tenant-c"),
        signer=signer,
    )

    assert first.exchange_identity != second.exchange_identity
    assert first.request.request_identity != second.request.request_identity


def test_replay_case_must_match_source_case(tmp_path: Path) -> None:
    request = CaseExchangeRequestV1.build(
        source_tenant_id="tenant-a",
        source_case_id=CaseId("CASE-WRONG"),
        recipient_tenant_id="tenant-b",
        recipient_case_id=CaseId("CASE-DEST-001"),
    )
    source_decision, source_resource, recipient_decision, recipient_resource = (
        _authorizations(request)
    )

    with pytest.raises(CaseExchangeV1Error, match="source case"):
        SignedCaseExchangeBundleV1.build(
            request=request,
            replay_bundle=_replay(tmp_path),
            source_decision=source_decision,
            source_resource=source_resource,
            recipient_decision=recipient_decision,
            recipient_resource=recipient_resource,
            signer=AttestationSigner.generate("wrong-case-key"),
            issued_at=1_000,
            expires_at=2_000,
            nonce="nonce",
        )


def test_recipient_requires_explicit_case_write_authorization(
    tmp_path: Path,
) -> None:
    request = _request()
    engine = _engine()
    source_decision, source_resource, _, recipient_resource = _authorizations(
        request
    )
    wrong_context = engine.build_context(
        subject_id="mallory",
        tenant_id=request.recipient_tenant_id,
        roles=("source-reader",),
        case_ids=(request.recipient_case_id.value,),
    )
    wrong_decision = engine.require(
        wrong_context,
        Permission.CASE_READ,
        recipient_resource,
        request_digest=request.request_identity.digest,
        strict_scope=True,
    )

    with pytest.raises(CaseExchangeV1Error, match="permission mismatch"):
        SignedCaseExchangeBundleV1.build(
            request=request,
            replay_bundle=_replay(tmp_path),
            source_decision=source_decision,
            source_resource=source_resource,
            recipient_decision=wrong_decision,
            recipient_resource=recipient_resource,
            signer=AttestationSigner.generate("permission-key"),
            issued_at=1_000,
            expires_at=2_000,
            nonce="nonce",
        )


def test_recipient_resource_scope_cannot_be_substituted(tmp_path: Path) -> None:
    request = _request()
    source_decision, source_resource, recipient_decision, _ = _authorizations(
        request
    )
    wrong_resource = ResourceDescriptor(
        resource_id="case-recipient",
        tenant_id="tenant-other",
        case_id=request.recipient_case_id.value,
        classification=DataClassification.CONFIDENTIAL,
    )

    with pytest.raises(CaseExchangeV1Error, match="resource digest mismatch"):
        SignedCaseExchangeBundleV1.build(
            request=request,
            replay_bundle=_replay(tmp_path),
            source_decision=source_decision,
            source_resource=source_resource,
            recipient_decision=recipient_decision,
            recipient_resource=wrong_resource,
            signer=AttestationSigner.generate("scope-key"),
            issued_at=1_000,
            expires_at=2_000,
            nonce="nonce",
        )


def test_tampered_replay_fails_before_attestation_acceptance(
    tmp_path: Path,
) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    replay = raw["replay_bundle"]
    assert isinstance(replay, dict)
    ledger = replay["ledger_bundle"]
    assert isinstance(ledger, dict)
    events = ledger["events"]
    assert isinstance(events, list)
    event = events[0]
    assert isinstance(event, dict)
    event["payload"] = {"tampered": True}
    _rebind_exchange_identity(raw)

    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )
    with pytest.raises(CaseExchangeV1Error):
        verify_signed_case_exchange(raw, verifier=verifier, now=1_500)


def test_request_rebinding_cannot_reuse_old_authorization(
    tmp_path: Path,
) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    request = raw["request"]
    assert isinstance(request, dict)
    request["recipient_case_id"] = "CASE-DEST-999"
    request_body = dict(request)
    request_body.pop("request_identity", None)
    request["request_identity"] = ContentAddress.for_value(
        request_body
    ).canonical_dict()
    _rebind_exchange_identity(raw)

    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )
    with pytest.raises(CaseExchangeV1Error, match="authorization"):
        verify_signed_case_exchange(raw, verifier=verifier, now=1_500)


def test_unknown_exchange_field_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    raw["future_magic"] = True

    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )
    with pytest.raises(CaseExchangeV1Error, match="unknown=future_magic"):
        verify_signed_case_exchange(raw, verifier=verifier, now=1_500)


def test_semantics_cannot_be_changed_to_truth_claim(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    raw["semantics"] = "attestation-is-epistemic-truth"
    _rebind_exchange_identity(raw)

    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )
    with pytest.raises(CaseExchangeV1Error, match="semantics"):
        verify_signed_case_exchange(raw, verifier=verifier, now=1_500)
    assert CASE_EXCHANGE_SEMANTICS_V1 == (
        "origin-integrity-only-not-epistemic-truth"
    )


def test_untrusted_or_revoked_key_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)

    untrusted = AttestationVerifier({})
    with pytest.raises(CaseExchangeV1Error, match="not trusted"):
        bundle.verify(verifier=untrusted, now=1_500)

    revoked = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()},
        revoked_key_ids=(signer.key_id,),
    )
    with pytest.raises(CaseExchangeV1Error, match="revoked"):
        bundle.verify(verifier=revoked, now=1_500)


def test_expired_attestation_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(
        tmp_path,
        issued_at=1_000,
        expires_at=1_100,
    )
    verifier = AttestationVerifier(
        {signer.key_id: signer.public_key_bytes()}
    )

    with pytest.raises(CaseExchangeV1Error, match="expired"):
        bundle.verify(verifier=verifier, now=1_100)


def test_exchange_module_has_no_ccl_write_or_persistence_authority() -> None:
    source = Path(exchange_module.__file__).read_text(encoding="utf-8")

    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
    assert "sqlite3" not in source
    assert "restore_case_bundle" not in source
