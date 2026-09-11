from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageEntryV1,
    ReplayRevalidationBaselineLineageError,
    ReplayRevalidationBaselineLineageV1,
    verify_revalidation_baseline_lineage_v1,
)
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionState,
    evaluate_revalidation_baseline_transition_v1,
)
from core.replay_revalidation_baseline_v1 import ReplayRevalidationBaselineV1
from core.replay_revalidation_fulfilment_v1 import evaluate_revalidation_fulfilment_v1
from core.replay_revalidation_invalidation_v1 import evaluate_revalidation_requirement_v1
from tests.test_replay_revalidation_baseline_transition_v1 import (
    _baseline,
    _changed_material,
    h,
)


def _unchanged_entry(
    baseline: ReplayRevalidationBaselineV1,
) -> ReplayRevalidationBaselineLineageEntryV1:
    candidate = baseline.fingerprint
    runtime = baseline.runtime_identity
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    return ReplayRevalidationBaselineLineageEntryV1(
        transition=evaluation.transition,
        resulting_baseline=evaluation.resulting_baseline,
    )


def _blocked_and_advanced_entries() -> tuple[
    ReplayRevalidationBaselineV1,
    ReplayRevalidationBaselineLineageEntryV1,
    ReplayRevalidationBaselineLineageEntryV1,
]:
    baseline, candidate, runtime, report = _changed_material()
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    blocked_fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    blocked_evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=blocked_fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    blocked = ReplayRevalidationBaselineLineageEntryV1(
        transition=blocked_evaluation.transition,
        resulting_baseline=blocked_evaluation.resulting_baseline,
    )

    fulfilled = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    advanced_evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilled,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    advanced = ReplayRevalidationBaselineLineageEntryV1(
        transition=advanced_evaluation.transition,
        resulting_baseline=advanced_evaluation.resulting_baseline,
    )
    assert blocked.transition.state is ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
    assert advanced.transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
    return baseline, blocked, advanced


def test_empty_lineage_derives_exact_genesis_and_round_trips() -> None:
    baseline, _ = _baseline()
    lineage = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)
    assert lineage.current_baseline == baseline
    assert lineage.current_baseline_digest == baseline.baseline_digest
    assert lineage.current_repository_sha == baseline.repository_sha
    assert lineage.transition_count == 0
    assert lineage.transition_digests == ()
    restored = ReplayRevalidationBaselineLineageV1.from_dict(lineage.canonical_dict())
    assert restored == lineage
    assert verify_revalidation_baseline_lineage_v1(restored) == lineage.lineage_digest


def test_blocked_then_advanced_then_reused_derives_current_verified_baseline() -> None:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    assert advanced.resulting_baseline is not None
    reused = _unchanged_entry(advanced.resulting_baseline)
    lineage = ReplayRevalidationBaselineLineageV1.build(
        genesis_baseline=baseline,
        entries=(blocked, advanced, reused),
    )
    assert lineage.transition_count == 3
    assert lineage.successful_transition_count == 2
    assert lineage.baseline_advance_count == 1
    assert lineage.blocked_attempt_count == 1
    assert lineage.current_baseline == advanced.resulting_baseline
    assert lineage.current_baseline_digest == advanced.resulting_baseline.baseline_digest
    assert lineage.current_repository_sha == advanced.resulting_baseline.repository_sha
    assert lineage.transition_digests == (
        blocked.transition.transition_digest,
        advanced.transition.transition_digest,
        reused.transition.transition_digest,
    )
    restored = ReplayRevalidationBaselineLineageV1.from_dict(lineage.canonical_dict())
    assert restored == lineage


def test_append_is_immutable_and_preserves_previous_lineage_identity() -> None:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    original = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)
    original_digest = original.lineage_digest
    with_blocked = original.append(blocked)
    with_advance = with_blocked.append(advanced)
    assert original.entries == ()
    assert original.lineage_digest == original_digest
    assert with_blocked.current_baseline == baseline
    assert with_advance.current_baseline == advanced.resulting_baseline
    assert len({original.lineage_digest, with_blocked.lineage_digest, with_advance.lineage_digest}) == 3


def test_reordered_entries_fail_closed_as_stale_parent() -> None:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="stale parent|fork"):
        ReplayRevalidationBaselineLineageV1.build(
            genesis_baseline=baseline,
            entries=(advanced, blocked),
        )


def test_forked_prior_baseline_fails_closed() -> None:
    baseline, blocked, _ = _blocked_and_advanced_entries()
    forked_transition = replace(
        blocked.transition,
        prior_baseline_digest=h("forked-prior-baseline"),
    )
    forked = ReplayRevalidationBaselineLineageEntryV1(
        transition=forked_transition,
        resulting_baseline=None,
    )
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="stale parent|fork"):
        ReplayRevalidationBaselineLineageV1.build(
            genesis_baseline=baseline,
            entries=(forked,),
        )


def test_duplicate_transition_replay_fails_closed() -> None:
    baseline, blocked, _ = _blocked_and_advanced_entries()
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="duplicate transition"):
        ReplayRevalidationBaselineLineageV1.build(
            genesis_baseline=baseline,
            entries=(blocked, blocked),
        )


def test_advanced_entry_requires_exact_resulting_baseline_bytes() -> None:
    baseline, _, advanced = _blocked_and_advanced_entries()
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="digest mismatch"):
        ReplayRevalidationBaselineLineageEntryV1(
            transition=advanced.transition,
            resulting_baseline=baseline,
        )


def test_blocked_entry_rejects_resulting_baseline_injection() -> None:
    baseline, blocked, _ = _blocked_and_advanced_entries()
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="blocked transition"):
        ReplayRevalidationBaselineLineageEntryV1(
            transition=blocked.transition,
            resulting_baseline=baseline,
        )


def test_canonical_summary_tamper_fails_closed() -> None:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    lineage = ReplayRevalidationBaselineLineageV1.build(
        genesis_baseline=baseline,
        entries=(blocked, advanced),
    )
    for field, value in (
        ("current_baseline_digest", h("tampered-head")),
        ("current_repository_sha", "f" * 40),
        ("transition_count", 99),
        ("baseline_advance_count", 99),
        ("blocked_attempt_count", 99),
        ("lineage_digest", h("tampered-lineage")),
    ):
        payload = copy.deepcopy(lineage.canonical_dict())
        payload[field] = value
        with pytest.raises(ReplayRevalidationBaselineLineageError):
            ReplayRevalidationBaselineLineageV1.from_dict(payload)


def test_nested_transition_tamper_fails_closed() -> None:
    baseline, blocked, _ = _blocked_and_advanced_entries()
    lineage = ReplayRevalidationBaselineLineageV1.build(
        genesis_baseline=baseline,
        entries=(blocked,),
    )
    payload = copy.deepcopy(lineage.canonical_dict())
    entries = payload["entries"]
    assert isinstance(entries, list)
    entry = entries[0]
    assert isinstance(entry, dict)
    transition = entry["transition"]
    assert isinstance(transition, dict)
    transition["candidate_repository_sha"] = "e" * 40
    with pytest.raises((ReplayRevalidationBaselineLineageError, ValueError)):
        ReplayRevalidationBaselineLineageV1.from_dict(payload)


def test_authority_and_unknown_field_injection_fail_closed() -> None:
    baseline, _ = _baseline()
    lineage = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)
    for authority in (
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
        "persistence_authority",
        "mutable_pointer_authority",
    ):
        payload = copy.deepcopy(lineage.canonical_dict())
        payload[authority] = True
        with pytest.raises(ReplayRevalidationBaselineLineageError, match="must remain false"):
            ReplayRevalidationBaselineLineageV1.from_dict(payload)
    payload = copy.deepcopy(lineage.canonical_dict())
    payload["latest_baseline_pointer"] = lineage.current_baseline_digest
    with pytest.raises(ReplayRevalidationBaselineLineageError, match="unknown"):
        ReplayRevalidationBaselineLineageV1.from_dict(payload)
