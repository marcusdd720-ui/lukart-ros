from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    AuthorityApproval,
    CaseAuthorityGrant,
    CaseProductHardeningError,
    ClosureAssessment,
    ClosureBlocker,
    DeltaAssertion,
    EpistemicLabel,
    ExternalActionIdentity,
    ExternalActionReceipt,
    IdempotencyConflictError,
    LegalEffectAssessment,
    LegalEffectStatus,
    ReceiptOutcome,
    ReopenDecision,
    ResponseClassification,
    ResponseDelta,
    ResponseSignal,
    TemporalLegalRule,
    close_case_governed,
    record_receipt_and_file_case,
    record_response_delta,
    reopen_case_governed,
    verify_receipt_for_transition,
)
from core.external_action_execution_v1 import (
    ReservationDisposition,
    SafeExternalActionCoordinator,
)
from core.p3.contracts import RuntimeIdentity
from knowledge.models.case import Case, CaseStatus

_SHA = "a" * 40
_DIGEST = "b" * 64


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=_SHA,
        schema_version="test.v1",
        config_digest=_DIGEST,
        corpus_digest="c" * 64,
    )


def _identity(
    *,
    case_id: str = "CASE-TEST-001",
    logical_action_id: str = "send-001",
    artifact_version: str = "v1",
    payload: str = "payload-v1",
) -> ExternalActionIdentity:
    return ExternalActionIdentity(
        case_id=CaseId(case_id),
        artifact_id=ObjectId("artifact-001"),
        artifact_version=artifact_version,
        artifact_digest=ContentAddress.for_value({"artifact": artifact_version}),
        logical_action_id=logical_action_id,
        action_type="FILE",
        channel="SYNTHETIC_PROVIDER",
        payload_digest=ContentAddress.for_value({"payload": payload}),
    )


def _receipt(
    identity: ExternalActionIdentity,
    *,
    receipt_id: str = "receipt-001",
    attempt_id: str = "attempt-001",
) -> ExternalActionReceipt:
    return ExternalActionReceipt.build(
        receipt_id=receipt_id,
        identity=identity,
        attempt_id=attempt_id,
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="synthetic-provider-receipt",
        provider_reference="provider-ref-001",
        external_timestamp=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
    )


def _approval(identity: ExternalActionIdentity) -> AuthorityApproval:
    return AuthorityApproval(
        approval_id="approval-001",
        actor_ref="synthetic-user",
        authority_basis="test-authority",
        scope="exact-artifact-and-action",
        case_id=identity.case_id,
        artifact_id=identity.artifact_id,
        artifact_version=identity.artifact_version,
        artifact_digest=identity.artifact_digest,
        action_type=identity.action_type,
        granted_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _case_authority(
    case_id: CaseId,
    *,
    actions: frozenset[str] = frozenset({"CASE_CLOSED", "CASE_REOPENED"}),
) -> CaseAuthorityGrant:
    return CaseAuthorityGrant(
        grant_id="case-authority-001",
        case_id=case_id,
        actor_ref="synthetic-user",
        authority_ref="test-authority",
        allowed_actions=actions,
        granted_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _rule(*, verified: bool = True, valid_to: date | None = None) -> TemporalLegalRule:
    now = datetime.now(UTC)
    return TemporalLegalRule(
        jurisdiction="PL-TEST",
        rule_id="synthetic-rule-001",
        source_ref="synthetic-authoritative-source",
        source_digest=ContentAddress.for_value({"rule": "synthetic"}),
        valid_from=date(2026, 1, 1),
        valid_to=valid_to,
        retrieved_at=now,
        verified_at=now,
        verification_method="synthetic-direct-verification",
        verified=verified,
    )


def test_receipt_integrity_accepts_exact_identity_and_rejects_wrong_version() -> None:
    identity = _identity()
    receipt = _receipt(identity)
    verify_receipt_for_transition(receipt, identity)

    changed = _identity(artifact_version="v2")
    with pytest.raises(CaseProductHardeningError):
        verify_receipt_for_transition(receipt, changed)


def test_receipt_from_other_case_is_rejected() -> None:
    identity = _identity(case_id="CASE-A")
    receipt = _receipt(identity)
    other_case = _identity(case_id="CASE-B")

    with pytest.raises(CaseProductHardeningError):
        verify_receipt_for_transition(receipt, other_case)


def test_receipt_unknown_cannot_promote_filed() -> None:
    identity = _identity()
    receipt = ExternalActionReceipt.build(
        receipt_id="receipt-unknown",
        identity=identity,
        attempt_id="attempt-unknown",
        outcome=ReceiptOutcome.UNKNOWN,
        evidence_ref="synthetic-timeout",
    )
    with pytest.raises(CaseProductHardeningError):
        verify_receipt_for_transition(receipt, identity)


def test_authority_is_bound_to_exact_artifact_digest() -> None:
    identity = _identity()
    approval = _approval(identity)
    assert approval.authorizes(identity)

    changed = ExternalActionIdentity(
        case_id=identity.case_id,
        artifact_id=identity.artifact_id,
        artifact_version=identity.artifact_version,
        artifact_digest=ContentAddress.for_value({"artifact": "changed"}),
        logical_action_id=identity.logical_action_id,
        action_type=identity.action_type,
        channel=identity.channel,
        payload_digest=identity.payload_digest,
    )
    assert not approval.authorizes(changed)


def test_idempotency_exact_retry_never_allows_second_invoke() -> None:
    identity = _identity()
    coordinator = SafeExternalActionCoordinator()

    first = coordinator.reserve(identity, attempt_id="attempt-001")
    assert first.disposition is ReservationDisposition.INVOKE_ALLOWED
    assert first.invoke_allowed

    concurrent = coordinator.reserve(identity, attempt_id="attempt-002")
    assert concurrent.disposition is ReservationDisposition.IN_PROGRESS
    assert not concurrent.invoke_allowed

    coordinator.confirm_success(
        identity,
        attempt_id="attempt-001",
        receipt=_receipt(identity),
    )
    retry = coordinator.reserve(identity, attempt_id="attempt-003")
    assert retry.disposition is ReservationDisposition.REPLAY_CONFIRMED
    assert not retry.invoke_allowed
    assert retry.record.receipt is not None


def test_idempotency_rejects_same_logical_id_with_changed_intent() -> None:
    coordinator = SafeExternalActionCoordinator()
    original = _identity(logical_action_id="logical-001", payload="one")
    changed = _identity(logical_action_id="logical-001", payload="two")

    coordinator.reserve(original, attempt_id="attempt-001")
    with pytest.raises(IdempotencyConflictError):
        coordinator.reserve(changed, attempt_id="attempt-002")


def test_idempotency_unknown_requires_reconciliation_before_retry() -> None:
    identity = _identity()
    coordinator = SafeExternalActionCoordinator()
    coordinator.reserve(identity, attempt_id="attempt-001")
    coordinator.mark_outcome_unknown(identity, attempt_id="attempt-001")

    retry = coordinator.reserve(identity, attempt_id="attempt-002")
    assert retry.disposition is ReservationDisposition.RECONCILE_REQUIRED
    assert not retry.invoke_allowed

    coordinator.confirm_no_effect(identity, reconciliation_ref="reconcile-no-effect")
    allowed = coordinator.reserve(identity, attempt_id="attempt-003")
    assert allowed.disposition is ReservationDisposition.INVOKE_ALLOWED


def test_timeout_after_acceptance_recovers_receipt_without_second_invoke() -> None:
    identity = _identity()
    coordinator = SafeExternalActionCoordinator()
    coordinator.reserve(identity, attempt_id="attempt-001")
    coordinator.mark_outcome_unknown(identity, attempt_id="attempt-001")

    recovered = coordinator.recover_receipt(
        identity,
        receipt=_receipt(identity),
        reconciliation_ref="provider-lookup-001",
    )
    assert recovered.receipt is not None

    retry = coordinator.reserve(identity, attempt_id="attempt-002")
    assert retry.disposition is ReservationDisposition.REPLAY_CONFIRMED
    assert not retry.invoke_allowed


def test_response_negation_cannot_be_final_resolution() -> None:
    with pytest.raises(CaseProductHardeningError):
        ResponseClassification.validate_candidate(
            response_text="Potwierdzamy odbiór. Nie wydano rozstrzygnięcia.",
            proposed_signals=(
                ResponseSignal.ACKNOWLEDGMENT,
                ResponseSignal.RESOLUTION_ISSUED,
                ResponseSignal.FINAL_RESOLUTION,
            ),
            evidence_refs=("response-001",),
            candidate_source="llm-proposer",
        )


def test_response_conflict_requires_explicit_unresolved() -> None:
    with pytest.raises(CaseProductHardeningError):
        ResponseClassification.validate_candidate(
            response_text="Synthetic conflicting response",
            proposed_signals=(
                ResponseSignal.RESOLUTION_ISSUED,
                ResponseSignal.NO_RESOLUTION,
            ),
            evidence_refs=("response-001",),
        )


def test_response_classification_allows_composable_nonfinal_signals() -> None:
    classification = ResponseClassification.validate_candidate(
        response_text="Odpowiadamy częściowo. Dalsza odpowiedź będzie później.",
        proposed_signals=(
            ResponseSignal.PARTIAL_RESPONSE,
            ResponseSignal.FUTURE_RESPONSE_PROMISED,
        ),
        evidence_refs=("response-001",),
    )
    assert ResponseSignal.PARTIAL_RESPONSE in classification.signals
    assert ResponseSignal.FUTURE_RESPONSE_PROMISED in classification.signals


def test_response_delta_preserves_claim_and_exact_base() -> None:
    classification = ResponseClassification.validate_candidate(
        response_text="Twierdzimy, że zdarzenie X miało miejsce.",
        proposed_signals=(ResponseSignal.SUBSTANTIVE_RESPONSE,),
        evidence_refs=("response-001",),
    )
    assertion = DeltaAssertion(
        statement="Adresat twierdzi, że X miało miejsce",
        label=EpistemicLabel.CLAIM,
        evidence_refs=("response-001",),
    )
    delta = ResponseDelta.build(
        case_id=CaseId("CASE-TEST-DELTA"),
        base_ledger_position=4,
        base_state_digest=ContentAddress.for_value({"state": 4}),
        classification=classification,
        assertions=(assertion,),
        contradictions=("X conflicts with earlier synthetic evidence",),
    )
    delta.verify()
    assert delta.assertions[0].label is EpistemicLabel.CLAIM
    assert delta.base_ledger_position == 4


def test_response_delta_rejects_stale_base_before_ledger_append(tmp_path) -> None:
    classification = ResponseClassification.validate_candidate(
        response_text="Synthetic response",
        proposed_signals=(ResponseSignal.INFORMATION_ONLY,),
        evidence_refs=("response-001",),
    )
    old_state = ContentAddress.for_value({"state": 1})
    current_state = ContentAddress.for_value({"state": 2})
    delta = ResponseDelta.build(
        case_id=CaseId("CASE-TEST-DELTA-STALE"),
        base_ledger_position=-1,
        base_state_digest=old_state,
        classification=classification,
    )

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(CaseProductHardeningError):
            record_response_delta(
                ledger,
                delta=delta,
                current_state_digest=current_state,
                current_ledger_position=-1,
                runtime_identity=_runtime(),
                expected_head=None,
                policy_version="response-delta.v1",
                actor_ref="system",
                authority_ref="deterministic-validator",
                correlation_id="corr-delta-001",
                causation_id="cause-delta-001",
            )
        assert ledger.events(delta.case_id) == ()


def test_fact_delta_requires_evidence() -> None:
    with pytest.raises(CaseProductHardeningError):
        DeltaAssertion(
            statement="X is a fact",
            label=EpistemicLabel.FACT,
            evidence_refs=(),
        )


def test_delivery_alone_does_not_prove_legal_effect() -> None:
    assessment = LegalEffectAssessment.assess(
        case_id=CaseId("CASE-TEST-EFFECT"),
        subject_ref="artifact-001",
        lifecycle_ref="RECEIVED/DELIVERED",
        rule=None,
        assessed_on=date(2026, 9, 13),
        prerequisites={},
        evidence_refs=("delivery-receipt",),
    )
    assert assessment.effect_status is LegalEffectStatus.UNKNOWN


def test_stale_legal_rule_does_not_prove_effect() -> None:
    assessment = LegalEffectAssessment.assess(
        case_id=CaseId("CASE-TEST-EFFECT"),
        subject_ref="artifact-001",
        lifecycle_ref="RECEIVED/DELIVERED",
        rule=_rule(valid_to=date(2026, 8, 31)),
        assessed_on=date(2026, 9, 13),
        prerequisites={"delivered": True},
        evidence_refs=("delivery-receipt",),
    )
    assert assessment.effect_status is LegalEffectStatus.UNKNOWN


def test_legal_effect_requires_verified_rule_and_prerequisites() -> None:
    assessment = LegalEffectAssessment.assess(
        case_id=CaseId("CASE-TEST-EFFECT"),
        subject_ref="artifact-001",
        lifecycle_ref="RECEIVED/DELIVERED",
        rule=_rule(),
        assessed_on=date(2026, 9, 13),
        prerequisites={"delivered": True, "formal_condition": True},
        evidence_refs=("delivery-receipt", "condition-evidence"),
        effective_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
    )
    assert assessment.effect_status is LegalEffectStatus.VERIFIED_EFFECTIVE
    assert assessment.effective_at is not None


def test_governed_filing_records_receipt_then_filed(tmp_path) -> None:
    identity = _identity(case_id="CASE-TEST-FILE")
    case = Case(id=identity.case_id.value, title="Synthetic filing")

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        receipt_event, filed_event = record_receipt_and_file_case(
            case,
            ledger,
            identity=identity,
            receipt=_receipt(identity),
            approval=_approval(identity),
            runtime_identity=_runtime(),
            expected_head=None,
            policy_version="case-filing.v1",
            correlation_id="corr-file-001",
            causation_id="cause-file-001",
        )
        events = ledger.events(identity.case_id)

    assert case.status is CaseStatus.FILED
    assert events == (receipt_event, filed_event)
    assert events[0].event_type == "EXTERNAL_ACTION_RECEIPT_RECORDED"
    assert events[1].event_type == "CASE_FILED"

    generic = Case(id="CASE-GENERIC", title="Generic")
    with pytest.raises(ValueError):
        generic.advance_to(CaseStatus.FILED)


def test_closure_blocks_material_open_items() -> None:
    assessment = ClosureAssessment.build(
        case_id=CaseId("CASE-TEST-CLOSE"),
        state_digest=ContentAddress.for_value({"state": "open"}),
        ledger_position=-1,
        blockers=(ClosureBlocker.OPEN_DEADLINE,),
        closure_reason="Synthetic closure review",
        actor_ref="synthetic-user",
        authority_ref="test-authority",
        policy_version="closure.v1",
    )
    assert not assessment.eligible


def test_unauthorized_closure_is_rejected(tmp_path) -> None:
    case_id = CaseId("CASE-TEST-NO-AUTH")
    case = Case(id=case_id.value, title="Synthetic unauthorized closure")
    state_digest = ContentAddress.for_value({"state": "clear"})
    assessment = ClosureAssessment.build(
        case_id=case_id,
        state_digest=state_digest,
        ledger_position=-1,
        blockers=(),
        closure_reason="Synthetic closure",
        actor_ref="synthetic-user",
        authority_ref="test-authority",
        policy_version="closure.v1",
    )
    wrong_authority = _case_authority(case_id, actions=frozenset({"CASE_REOPENED"}))

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(CaseProductHardeningError):
            close_case_governed(
                case,
                ledger,
                assessment=assessment,
                authority=wrong_authority,
                current_state_digest=state_digest,
                current_ledger_position=-1,
                runtime_identity=_runtime(),
                expected_head=None,
                correlation_id="corr-close-auth",
                causation_id="cause-close-auth",
            )
        assert ledger.events(case_id) == ()


def test_governed_close_and_append_only_reopen_create_new_epoch(tmp_path) -> None:
    case_id = CaseId("CASE-TEST-CLOSE")
    case = Case(id=case_id.value, title="Synthetic closure", status=CaseStatus.ANALYSIS)
    state_digest = ContentAddress.for_value({"state": "clear"})
    authority = _case_authority(case_id)
    assessment = ClosureAssessment.build(
        case_id=case_id,
        state_digest=state_digest,
        ledger_position=-1,
        blockers=(),
        closure_reason="All synthetic blockers cleared",
        actor_ref="synthetic-user",
        authority_ref="test-authority",
        policy_version="closure.v1",
        lifecycle_epoch=0,
    )

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        closed = close_case_governed(
            case,
            ledger,
            assessment=assessment,
            authority=authority,
            current_state_digest=state_digest,
            current_ledger_position=-1,
            runtime_identity=_runtime(),
            expected_head=None,
            correlation_id="corr-close-001",
            causation_id="cause-close-001",
        )
        assert case.status is CaseStatus.CLOSED

        decision = ReopenDecision.build(
            case_id=case_id,
            previous_epoch=0,
            reason="Material synthetic response arrived after closure",
            actor_ref="synthetic-user",
            authority_ref="test-authority",
        )
        reopened = reopen_case_governed(
            case,
            ledger,
            decision=decision,
            authority=authority,
            runtime_identity=_runtime(),
            expected_head=closed.event_id,
            policy_version="reopen.v1",
            correlation_id="corr-reopen-001",
            causation_id=closed.event_id.digest,
        )
        events = ledger.events(case_id)

    assert [event.event_type for event in events] == ["CASE_CLOSED", "CASE_REOPENED"]
    assert reopened.previous_event_id == closed.event_id
    assert case.status is CaseStatus.ANALYSIS
    assert case.metadata["lifecycle_epoch"] == 1


def test_stale_closure_assessment_is_rejected(tmp_path) -> None:
    case_id = CaseId("CASE-TEST-STALE-CLOSE")
    case = Case(id=case_id.value, title="Synthetic stale closure")
    old_state = ContentAddress.for_value({"state": 1})
    current_state = ContentAddress.for_value({"state": 2})
    assessment = ClosureAssessment.build(
        case_id=case_id,
        state_digest=old_state,
        ledger_position=-1,
        blockers=(),
        closure_reason="Synthetic assessment",
        actor_ref="synthetic-user",
        authority_ref="test-authority",
        policy_version="closure.v1",
    )

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(CaseProductHardeningError):
            close_case_governed(
                case,
                ledger,
                assessment=assessment,
                authority=_case_authority(case_id),
                current_state_digest=current_state,
                current_ledger_position=-1,
                runtime_identity=_runtime(),
                expected_head=None,
                correlation_id="corr-stale-001",
                causation_id="cause-stale-001",
            )
        assert ledger.events(case_id) == ()
