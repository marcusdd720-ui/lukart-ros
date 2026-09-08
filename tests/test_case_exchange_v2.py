from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.case_exchange_v1 import CaseExchangeRequestV1, SignedCaseExchangeBundleV1
from core.case_exchange_v2 import (
    CaseExchangeV2Error,
    SignedCaseExchangeBundleV2,
    verify_signed_case_exchange_v2,
)
from core.case_ledger import CanonicalCaseLedger, CaseId, ObjectId
from core.case_ledger.contracts import ContentAddress
from core.case_replay_v2 import CaseReplayBundleV2
from core.enterprise.authorization import AuthorizationEngine, ResourceDescriptor, RoleDefinition
from core.enterprise.authorization_policy import AuthorizationPolicyV1
from core.enterprise.contracts import (
    AttestationSigner,
    AttestationVerifier,
    AuthorizationContext,
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
    case_id = CaseId("CASE-XCH2-SOURCE")
    with CanonicalCaseLedger(tmp_path / "xch2.db") as ledger:
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-XCH2-1"),
            assertion_type="claim.v1",
            content={"value": "portable-authorization"},
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


def _request() -> CaseExchangeRequestV1:
    return CaseExchangeRequestV1.build(
        source_tenant_id="tenant-source",
        source_case_id=CaseId("CASE-XCH2-SOURCE"),
        recipient_tenant_id="tenant-recipient",
        recipient_case_id=CaseId("CASE-XCH2-DEST"),
    )


def _contexts_and_resources(
    request: CaseExchangeRequestV1,
    engine: AuthorizationEngine,
) -> tuple[
    AuthorizationContext,
    ResourceDescriptor,
    AuthorizationContext,
    ResourceDescriptor,
]:
    source_context = engine.build_context(
        subject_id="source-user",
        tenant_id=request.source_tenant_id,
        roles=("source-reader",),
        case_ids=(request.source_case_id.value,),
    )
    recipient_context = engine.build_context(
        subject_id="recipient-user",
        tenant_id=request.recipient_tenant_id,
        roles=("recipient-writer",),
        case_ids=(request.recipient_case_id.value,),
    )
    source_resource = ResourceDescriptor(
        resource_id="source-case",
        tenant_id=request.source_tenant_id,
        case_id=request.source_case_id.value,
        classification=DataClassification.CONFIDENTIAL,
    )
    recipient_resource = ResourceDescriptor(
        resource_id="recipient-case",
        tenant_id=request.recipient_tenant_id,
        case_id=request.recipient_case_id.value,
        classification=DataClassification.CONFIDENTIAL,
    )
    return source_context, source_resource, recipient_context, recipient_resource


def _bundle(
    tmp_path: Path,
    *,
    signer: AttestationSigner | None = None,
    nonce: str = "xch2-nonce",
) -> tuple[SignedCaseExchangeBundleV2, AttestationSigner]:
    request = _request()
    engine = _engine()
    source_context, source_resource, recipient_context, recipient_resource = (
        _contexts_and_resources(request, engine)
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
    active_signer = signer or AttestationSigner.generate("xch2-key")
    signed_v1 = SignedCaseExchangeBundleV1.build(
        request=request,
        replay_bundle=_replay(tmp_path),
        source_decision=source_decision,
        source_resource=source_resource,
        recipient_decision=recipient_decision,
        recipient_resource=recipient_resource,
        signer=active_signer,
        issued_at=1_000,
        expires_at=2_000,
        nonce=nonce,
    )
    policy = engine.policy_snapshot()
    return (
        SignedCaseExchangeBundleV2.build(
            signed_exchange_v1=signed_v1,
            source_policy=policy,
            source_context=source_context,
            recipient_policy=policy,
            recipient_context=recipient_context,
        ),
        active_signer,
    )


def _serialized(bundle: SignedCaseExchangeBundleV2) -> dict[str, object]:
    decoded = json.loads(canonical_json(bundle.canonical_dict()))
    assert isinstance(decoded, dict)
    return decoded


def _rebind_proof(raw_proof: dict[str, object]) -> None:
    body = dict(raw_proof)
    body.pop("proof_identity", None)
    raw_proof["proof_identity"] = ContentAddress.for_value(body).canonical_dict()


def _rebind_v2(raw: dict[str, object]) -> None:
    body = dict(raw)
    body.pop("exchange_identity", None)
    raw["exchange_identity"] = ContentAddress.for_value(body).canonical_dict()


def _verifier(signer: AttestationSigner) -> AttestationVerifier:
    return AttestationVerifier({signer.key_id: signer.public_key_bytes()})


def test_v2_verifies_xch1_and_recomputes_both_historical_authorizations(
    tmp_path: Path,
) -> None:
    bundle, signer = _bundle(tmp_path)

    result = bundle.verify(verifier=_verifier(signer), now=1_500)

    assert result.exchange_identity == bundle.exchange_identity
    assert result.signed_exchange_v1_identity.digest
    assert result.replay_bundle_identity.digest
    assert result.source_policy_digest == bundle.source_authorization_proof.policy.policy_digest
    assert result.recipient_policy_digest == (
        bundle.recipient_authorization_proof.policy.policy_digest
    )
    assert result.source_context_digest == (
        bundle.signed_exchange_v1["source_authorization"]["context_digest"]
    )
    assert result.recipient_context_digest == (
        bundle.signed_exchange_v1["recipient_authorization"]["context_digest"]
    )


def test_same_inputs_produce_same_v2_identity(tmp_path: Path) -> None:
    signer = AttestationSigner.generate("deterministic-xch2-key")
    first, _ = _bundle(tmp_path / "first", signer=signer, nonce="same-nonce")
    second, _ = _bundle(tmp_path / "second", signer=signer, nonce="same-nonce")

    assert first.exchange_identity == second.exchange_identity
    assert first.canonical_dict() == second.canonical_dict()


def test_policy_preimage_substitution_fails_even_after_rebinding_wrapper(
    tmp_path: Path,
) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    source_proof = raw["source_authorization_proof"]
    assert isinstance(source_proof, dict)

    replacement = AuthorizationPolicyV1.build(
        (
            RoleDefinition(
                role="source-reader",
                permissions=(Permission.CASE_READ, Permission.CASE_WRITE),
                max_classification=DataClassification.RESTRICTED,
            ),
            RoleDefinition(
                role="recipient-writer",
                permissions=(Permission.CASE_WRITE,),
                max_classification=DataClassification.RESTRICTED,
            ),
        )
    )
    source_proof["policy"] = replacement.canonical_dict()
    _rebind_proof(source_proof)
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error, match="policy digest mismatch"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_context_role_substitution_fails_after_rebinding_wrapper(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    source_proof = raw["source_authorization_proof"]
    assert isinstance(source_proof, dict)
    context = source_proof["context"]
    assert isinstance(context, dict)
    context["roles"] = ["recipient-writer"]
    _rebind_proof(source_proof)
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error, match="context digest mismatch"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_source_and_recipient_proofs_cannot_be_swapped(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    source = raw["source_authorization_proof"]
    recipient = raw["recipient_authorization_proof"]
    raw["source_authorization_proof"] = recipient
    raw["recipient_authorization_proof"] = source
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error, match="party mismatch"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_unknown_v2_field_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    raw["future_magic"] = True

    with pytest.raises(CaseExchangeV2Error, match="unknown=future_magic"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_future_policy_schema_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    source_proof = raw["source_authorization_proof"]
    assert isinstance(source_proof, dict)
    policy = source_proof["policy"]
    assert isinstance(policy, dict)
    policy["schema"] = "lukart.authorization-policy.v999"
    _rebind_proof(source_proof)
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error, match="unsupported authorization policy schema"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_noncanonical_context_fails_closed(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    source_proof = raw["source_authorization_proof"]
    assert isinstance(source_proof, dict)
    context = source_proof["context"]
    assert isinstance(context, dict)
    context["case_ids"] = ["CASE-Z", "CASE-A"]
    _rebind_proof(source_proof)
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error, match="non-canonical"):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_v1_signature_still_rejects_inner_exchange_tampering(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)
    raw = _serialized(bundle)
    signed_v1 = raw["signed_exchange_v1"]
    assert isinstance(signed_v1, dict)
    request = signed_v1["request"]
    assert isinstance(request, dict)
    request["recipient_tenant_id"] = "tenant-attacker"
    _rebind_v2(raw)

    with pytest.raises(CaseExchangeV2Error):
        verify_signed_case_exchange_v2(raw, verifier=_verifier(signer), now=1_500)


def test_expired_xch1_signature_fails_v2_verification(tmp_path: Path) -> None:
    bundle, signer = _bundle(tmp_path)

    with pytest.raises(CaseExchangeV2Error):
        bundle.verify(verifier=_verifier(signer), now=2_001)
