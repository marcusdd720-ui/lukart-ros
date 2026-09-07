from __future__ import annotations

from pathlib import Path

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, DigestAlgorithm, ObjectId
from core.p3.contracts import RuntimeIdentity
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import (
    ASSERTION_TRANSITION_EVENT_V1,
    EpistemicDecisionV2,
    EpistemicLedgerService,
    EpistemicPolicyV2,
    EpistemicProjectionV2,
    EpistemicV2Error,
    EvidenceEventRef,
)


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="epistemic.v2",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        provider_inventory_declared=True,
    )


def _ledger(tmp_path: Path) -> CanonicalCaseLedger:
    return CanonicalCaseLedger(tmp_path / "canonical.db")


def _evidence(
    ledger: CanonicalCaseLedger,
    case_id: CaseId,
    *,
    expected_head: ContentAddress | None,
    event_type: str = "evidence.ingested.v1",
) -> ContentAddress:
    event = ledger.append_event(
        case_id=case_id,
        event_type=event_type,
        runtime_identity=_runtime(),
        payload={"source": "fixture", "digest": "d" * 64},
        expected_head=expected_head,
    )
    return event.event_id


def test_phx03_policy_identity_is_deterministic_and_binds_legacy_transition_policy() -> None:
    first = EpistemicPolicyV2.reference()
    second = EpistemicPolicyV2.reference()

    assert first == second
    assert str(first.policy_identity).startswith("sha256:")
    assert first.canonical_body()["transition_policy"]
    assert first.canonical_body()["authoritative_state_source"] == "canonical-case-ledger"


def test_claim_is_written_only_through_ccl_and_projection_is_deterministic(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-001")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-001"),
            assertion_type="ownership.claim.v1",
            content={"owner": "A"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )

        first = service.project(case_id)
        second = service.project(case_id)
        state = first.get(assertion.assertion_id)

        assert first == second
        assert state is not None
        assert state.status is KnowledgeStatus.CLAIM
        assert len(ledger.events(case_id)) == 1
        assert ledger.events(case_id)[0].event_type == "epistemic.assertion.created.v1"


def test_initial_fact_requires_exact_prior_authorized_evidence_event(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-FACT")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)

        with pytest.raises(EpistemicV2Error, match="FACT requires exact prior evidence"):
            service.create_assertion(
                case_id=case_id,
                subject_id=ObjectId("OBJ-FACT"),
                assertion_type="fact.v1",
                content={"value": 1},
                initial_status=KnowledgeStatus.FACT,
                evidence_refs=(),
                runtime_identity=_runtime(),
                expected_head=None,
            )

        evidence_id = _evidence(ledger, case_id, expected_head=None)
        ref = EvidenceEventRef(case_id=case_id, event_id=evidence_id)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-FACT"),
            assertion_type="fact.v1",
            content={"value": 1},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(ref,),
            runtime_identity=_runtime(),
            expected_head=evidence_id,
        )

        state = service.project(case_id).get(assertion.assertion_id)
        assert state is not None
        assert state.status is KnowledgeStatus.FACT
        assert state.evidence_refs == (ref,)


def test_claim_to_fact_requires_resolved_evidence_and_records_policy_decision(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-PROMOTE")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-PROMOTE"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        assertion_head = ledger.head(case_id)
        assert assertion_head is not None
        evidence_id = _evidence(ledger, case_id, expected_head=assertion_head)
        ref = EvidenceEventRef(case_id=case_id, event_id=evidence_id)

        decision = service.transition(
            case_id=case_id,
            assertion_id=assertion.assertion_id,
            target=KnowledgeStatus.FACT,
            evidence_refs=(ref,),
            runtime_identity=_runtime(),
            expected_head=evidence_id,
        )

        projected = service.project(case_id).get(assertion.assertion_id)
        assert decision.allowed is True
        assert projected is not None
        assert projected.status is KnowledgeStatus.FACT
        assert projected.last_decision_id == decision.decision_id


def test_unresolved_fake_evidence_denies_fact_without_writing(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-FAKE")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-FAKE"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        head = ledger.head(case_id)
        assert head is not None
        fake = EvidenceEventRef(
            case_id=case_id,
            event_id=ContentAddress(algorithm=DigestAlgorithm.SHA256, digest="f" * 64),
        )

        decision = service.decide_transition(
            case_id=case_id,
            assertion_id=assertion.assertion_id,
            target=KnowledgeStatus.FACT,
            evidence_refs=(fake,),
        )
        assert decision.allowed is False
        assert "does not resolve" in decision.reason

        with pytest.raises(EpistemicV2Error, match="does not resolve"):
            service.transition(
                case_id=case_id,
                assertion_id=assertion.assertion_id,
                target=KnowledgeStatus.FACT,
                evidence_refs=(fake,),
                runtime_identity=_runtime(),
                expected_head=head,
            )
        assert ledger.head(case_id) == head


def test_non_evidence_event_cannot_be_used_for_fact_promotion(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-TYPE")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-TYPE"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        head = ledger.head(case_id)
        assert head is not None
        wrong_type = _evidence(
            ledger,
            case_id,
            expected_head=head,
            event_type="reasoning.output.v1",
        )
        ref = EvidenceEventRef(case_id=case_id, event_id=wrong_type)

        decision = service.decide_transition(
            case_id=case_id,
            assertion_id=assertion.assertion_id,
            target=KnowledgeStatus.FACT,
            evidence_refs=(ref,),
        )
        assert decision.allowed is False
        assert "unauthorized event type" in decision.reason


def test_cross_case_evidence_fails_closed(tmp_path: Path) -> None:
    case_a = CaseId("CASE-A")
    case_b = CaseId("CASE-B")
    with _ledger(tmp_path) as ledger:
        evidence_id = _evidence(ledger, case_b, expected_head=None)
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_a,
            subject_id=ObjectId("OBJ-A"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        ref = EvidenceEventRef(case_id=case_b, event_id=evidence_id)

        decision = service.decide_transition(
            case_id=case_a,
            assertion_id=assertion.assertion_id,
            target=KnowledgeStatus.FACT,
            evidence_refs=(ref,),
        )
        assert decision.allowed is False
        assert "cross-case evidence" in decision.reason


def test_noop_transition_is_denied_and_does_not_append(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-NOOP")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-NOOP"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        head = ledger.head(case_id)
        assert head is not None

        with pytest.raises(EpistemicV2Error, match="no-op"):
            service.transition(
                case_id=case_id,
                assertion_id=assertion.assertion_id,
                target=KnowledgeStatus.CLAIM,
                runtime_identity=_runtime(),
                expected_head=head,
            )
        assert ledger.head(case_id) == head


def test_manual_policy_violating_transition_is_rejected_by_reducer(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-MALICIOUS")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        assertion = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-MALICIOUS"),
            assertion_type="claim.v1",
            content={"value": "x"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        head = ledger.head(case_id)
        assert head is not None
        forged = EpistemicDecisionV2.build(
            assertion_id=assertion.assertion_id,
            source=KnowledgeStatus.CLAIM,
            target=KnowledgeStatus.FACT,
            evidence_refs=(),
            rationale="forged",
            policy=service.policy,
            allowed=True,
            reason="evidence-backed promotion to FACT",
        )
        ledger.append_event(
            case_id=case_id,
            event_type=ASSERTION_TRANSITION_EVENT_V1,
            runtime_identity=_runtime(),
            payload={"decision": forged.canonical_dict()},
            expected_head=head,
            object_id=ObjectId("OBJ-MALICIOUS"),
        )

        with pytest.raises(EpistemicV2Error, match="FACT requires exact prior evidence"):
            service.project(case_id)


def test_unknown_epistemic_event_type_fails_closed(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-UNKNOWN")
    with _ledger(tmp_path) as ledger:
        ledger.append_event(
            case_id=case_id,
            event_type="epistemic.future.unknown.v99",
            runtime_identity=_runtime(),
            payload={"future": True},
            expected_head=None,
        )

        with pytest.raises(EpistemicV2Error, match="unknown epistemic event type"):
            EpistemicProjectionV2.build(
                case_id=case_id,
                events=ledger.events(case_id),
                policy=EpistemicPolicyV2.reference(),
            )


def test_stale_head_rejects_epistemic_write(tmp_path: Path) -> None:
    case_id = CaseId("CASE-EP-STALE")
    with _ledger(tmp_path) as ledger:
        service = EpistemicLedgerService(ledger)
        first = service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-1"),
            assertion_type="claim.v1",
            content={"value": 1},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=_runtime(),
            expected_head=None,
        )
        assert first.assertion_id

        with pytest.raises(EpistemicV2Error, match="lost exact canonical ledger head"):
            service.create_assertion(
                case_id=case_id,
                subject_id=ObjectId("OBJ-2"),
                assertion_type="claim.v1",
                content={"value": 2},
                initial_status=KnowledgeStatus.CLAIM,
                evidence_refs=(),
                runtime_identity=_runtime(),
                expected_head=None,
            )
        assert len(ledger.events(case_id)) == 1
