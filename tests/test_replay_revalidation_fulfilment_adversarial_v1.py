from __future__ import annotations

import copy

import pytest

from core.cross_environment_replay_v1 import (
    ReplayExecutionStatus,
    build_replay_receipt,
    build_replay_report,
)
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentError,
    ReplayRevalidationFulfilmentState,
    ReplayRevalidationFulfilmentV1,
    evaluate_revalidation_fulfilment_v1,
)
from test_replay_revalidation_fulfilment_v1 import _material, h


def _evaluate(
    *,
    replay_report: dict[str, object] | None,
    replay_repository_sha: str | None,
    candidate_repository_sha: str | None = None,
):
    baseline_runtime, candidate_runtime, baseline, candidate, decision, _ = _material()
    return evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
        candidate_repository_sha=candidate_repository_sha or candidate_runtime.code_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )


def test_candidate_repository_sha_substitution_fails_closed() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="repository SHA/RuntimeIdentity substitution",
    ):
        _evaluate(
            replay_report=report,
            replay_repository_sha=candidate_runtime.code_sha,
            candidate_repository_sha="c" * 40,
        )


def test_stale_replay_sha_cannot_be_relabelled_as_candidate_evidence() -> None:
    _, _, _, _, _, report = _material()
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="not produced for the exact candidate",
    ):
        _evaluate(replay_report=report, replay_repository_sha="a" * 40)


def test_tampered_replay_report_fails_before_fulfilment_claim() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    tampered = copy.deepcopy(report)
    receipts = tampered["receipts"]
    assert isinstance(receipts, list)
    assert isinstance(receipts[0], dict)
    receipts[0]["semantic_result_identity"] = h("tampered-semantic")
    with pytest.raises(ReplayRevalidationFulfilmentError, match="invalid LRD-01K replay evidence"):
        _evaluate(
            replay_report=tampered,
            replay_repository_sha=candidate_runtime.code_sha,
        )


def test_valid_semantic_drift_report_is_revalidation_failed_not_pass() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    plan = report["plan"]
    profiles = report["profiles"]
    observed = report["observed_environments"]
    assert isinstance(plan, dict)
    assert isinstance(profiles, list)
    assert isinstance(observed, list)
    observed_by_profile = {
        str(item["declared_profile_digest"]): item
        for item in observed
        if isinstance(item, dict)
    }
    receipts: list[dict[str, object]] = []
    for profile in profiles:
        assert isinstance(profile, dict)
        profile_digest = str(profile["profile_digest"])
        observation = observed_by_profile[profile_digest]
        receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observation,
                verifier_digest=str(profile["replay_verifier_digest"]),
                semantic_result_identity=h("semantic-drift"),
                invariant_report_identity=h("invariants-drift"),
                lrd01d_classification="SEMANTIC_DRIFT",
                execution_status=ReplayExecutionStatus.VERIFIED,
            )
        )
    failed_report = build_replay_report(
        plan=plan,
        profiles=profiles,
        observed_environments=observed,
        receipts=receipts,
    )
    result = _evaluate(
        replay_report=failed_report,
        replay_repository_sha=candidate_runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.REVALIDATION_FAILED
    assert result.revalidation_satisfied is False
    assert all("SEMANTIC_DRIFT" in violation for violation in result.violations)


def test_partial_replay_binding_is_rejected() -> None:
    _, _, _, _, _, report = _material()
    with pytest.raises(ReplayRevalidationFulfilmentError, match="supplied together"):
        _evaluate(replay_report=report, replay_repository_sha=None)


def test_fulfilment_parser_rejects_authority_injection_and_digest_tamper() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    result = _evaluate(
        replay_report=report,
        replay_repository_sha=candidate_runtime.code_sha,
    )
    authority = result.canonical_dict()
    authority["release_authority"] = True
    with pytest.raises(ReplayRevalidationFulfilmentError, match="release_authority"):
        ReplayRevalidationFulfilmentV1.from_dict(authority)

    tampered = result.canonical_dict()
    tampered["state"] = "REVALIDATION_FAILED"
    with pytest.raises(ReplayRevalidationFulfilmentError):
        ReplayRevalidationFulfilmentV1.from_dict(tampered)


def test_uppercase_repository_sha_is_never_canonical() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    with pytest.raises(ReplayRevalidationFulfilmentError, match="lowercase 40-char git SHA"):
        _evaluate(
            replay_report=report,
            replay_repository_sha=candidate_runtime.code_sha,
            candidate_repository_sha=candidate_runtime.code_sha.upper(),
        )
