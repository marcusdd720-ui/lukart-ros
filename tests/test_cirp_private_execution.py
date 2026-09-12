from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast

import pytest

import core.cirp.intake as intake
from core.cirp.contracts import (
    CIRPContractError,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
    RulePackStatus,
)
from core.cirp.governance import (
    RulePackApproval,
    RulePackFreshnessPolicy,
    RulePackRegistry,
)
from core.cirp.private_execution import PrivateCIRPExecutionReceipt, run_private_case
from core.private_evidence_v1 import PrivateEvidenceStore
from tests.test_cirp_private_intake import CONFIG, NOW, _draft_request, _projection


def _store() -> PrivateEvidenceStore:
    return cast(PrivateEvidenceStore, object())


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    request=None,
    registry: RulePackRegistry | None = None,
    freshness_policy: RulePackFreshnessPolicy | None = None,
):
    monkeypatch.setattr(intake, "load_verified_projection", lambda store: _projection())
    return run_private_case(
        _store(),
        request or _draft_request(),
        document_ids=("DOC-001",),
        policy_identity="policy:cirp-p04:synthetic:v1",
        runtime_identity="runtime:cirp-p04:private-execution:v1",
        evaluation_time=NOW,
        source_configuration_digest=CONFIG,
        registry=registry,
        freshness_policy=freshness_policy,
    )


def _governed_request() -> tuple[
    object,
    RulePackRegistry,
    RulePackFreshnessPolicy,
]:
    source = LegalSourceRef(
        source_id="source:cirp:p04:synthetic",
        jurisdiction="PL",
        authority_type="synthetic",
        formal_citation="Synthetic source for CIRP-P04",
        source_uri="https://example.invalid/cirp-p04",
        source_digest="9" * 64,
        effective_from=date(2026, 1, 1),
        effective_until=None,
        retrieved_at=NOW,
        verification_status=LegalSourceVerificationStatus.VERIFIED,
    )
    pack = ProceduralRulePack.build(
        pack_id="pack:cirp:p04:synthetic",
        version="1",
        jurisdiction="PL",
        procedure_family="synthetic_p04",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        status=RulePackStatus.ACTIVE,
    )
    request = replace(_draft_request(), rule_packs=(pack,))
    registry = RulePackRegistry(
        registry_id="registry:cirp:p04:synthetic",
        version="1",
        approvals=(
            RulePackApproval(
                approval_id="approval:cirp:p04:synthetic",
                pack_id=pack.pack_id,
                pack_digest=pack.digest(),
                verified_at=NOW,
                approved_by="governance:cirp:p04:synthetic",
            ),
        ),
    )
    policy = RulePackFreshnessPolicy(
        policy_id="freshness:cirp:p04:synthetic",
        version="1",
        max_approval_age_days=30,
        max_source_age_days=30,
        require_verified_sources=True,
    )
    return request, registry, policy


def test_private_execution_is_one_step_deterministic_and_privacy_minimized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _run(monkeypatch)
    second = _run(monkeypatch)

    assert first.receipt.digest() == second.receipt.digest()
    assert first.receipt.run_identity_digest == (
        first.governed_result.canonical_result.run_identity.digest()
    )
    assert first.receipt.report_digest == first.governed_result.canonical_result.report.digest()
    assert first.receipt.canonical_replay_digest == (
        first.governed_result.canonical_result.replay_manifest.digest()
    )
    assert first.receipt.governance_receipt_digest is None
    assert first.receipt.governed_replay_digest is None

    serialized_receipt = str(first.receipt.canonical_dict())
    for private_marker in (
        "CASE-SYNTHETIC-P02",
        "DOC-001",
        "Synthetic Authority",
        "Synthetic private intake",
    ):
        assert private_marker not in serialized_receipt


def test_private_execution_carries_exact_rule_pack_governance_into_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, registry, policy = _governed_request()

    result = _run(
        monkeypatch,
        request=request,
        registry=registry,
        freshness_policy=policy,
    )

    assert result.governed_result.governance_receipt is not None
    assert result.governed_result.replay_manifest is not None
    assert result.receipt.governance_receipt_digest == (
        result.governed_result.governance_receipt.digest()
    )
    assert result.receipt.governed_replay_digest == (
        result.governed_result.replay_manifest.digest()
    )
    assert result.governed_result.governance_receipt.run_identity_digest == (
        result.receipt.run_identity_digest
    )


def test_private_execution_with_rule_pack_but_without_governance_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _ = _governed_request()

    with pytest.raises(CIRPContractError, match="require registry approval"):
        _run(monkeypatch, request=request)


def test_private_execution_receipt_rejects_partial_governance_binding() -> None:
    with pytest.raises(CIRPContractError, match="must be present together"):
        PrivateCIRPExecutionReceipt(
            run_identity_digest="1" * 64,
            report_digest="2" * 64,
            canonical_replay_digest="3" * 64,
            governance_receipt_digest="4" * 64,
            governed_replay_digest=None,
        )
