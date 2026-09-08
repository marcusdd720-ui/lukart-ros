from __future__ import annotations

from pathlib import Path

import pytest

from core.case_ledger import CaseId, ContentAddress, DigestAlgorithm
from core.evaluation import (
    CaseLedgerHead,
    EvaluationContractError,
    EvaluationInputIdentity,
    EvaluationPurpose,
    EvaluatorIdentity,
    GoldCorpusIdentity,
    GoldSplit,
    KQMDeltaDirection,
    KQMLongitudinalPoint,
    KQMPolicy,
    KQMProjection,
    PersistentKQMHistory,
    compare_kqm_points,
)
from core.p3.contracts import P3ContractError, RuntimeIdentity
from validation.gold_kqm_v2 import load_gold_corpus_identity, load_kqm_policy

GOLD_PATH = Path("data/quality/post_v1_gold_v1_1.json")
MANIFEST_PATH = Path("data/quality/post_v1_gold_v1_1.manifest.json")
KQM_PATH = Path("config/post_hardcore_kqm_v2.json")


def _runtime(
    *,
    code_char: str,
    provider: str = "provider-a@1",
    complete: bool = True,
) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code_char * 40,
        schema_version="evaluation.v2",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=(provider,),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=("e" * 64,),
        provider_inventory_declared=True,
        plugin_inventory_declared=complete,
        input_inventory_declared=complete,
        evidence_inventory_declared=complete,
        dependency_lock_digest="f" * 64 if complete else "",
        python_implementation="CPython" if complete else "",
        python_version="3.11.9" if complete else "",
        platform_tag="linux-x86_64" if complete else "",
        project_version="1.1.0.dev0" if complete else "",
        build_backend="lukart_build_backend" if complete else "",
        execution_environment_declared=complete,
    )


def _evaluator() -> EvaluatorIdentity:
    return EvaluatorIdentity.build(
        evaluator_id="lukart-kqm-reference",
        evaluator_version="2.0.0",
        code_sha="a" * 40,
        runtime_identity=_runtime(code_char="1"),
    )


def _ledger_heads(
    corpus: GoldCorpusIdentity,
    *,
    digest_offset: int = 1,
) -> tuple[CaseLedgerHead, ...]:
    case_ids = corpus.split_case_ids[GoldSplit.DEVELOPMENT]
    return tuple(
        CaseLedgerHead(
            case_id=CaseId(case_id),
            head_event_id=ContentAddress(
                algorithm=DigestAlgorithm.SHA256,
                digest=f"{index + digest_offset:064x}",
            ),
        )
        for index, case_id in enumerate(case_ids)
    )


def _context(
    *,
    digest_offset: int = 1,
) -> tuple[
    GoldCorpusIdentity,
    KQMPolicy,
    EvaluatorIdentity,
    EvaluationInputIdentity,
]:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    evaluation_input = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.DEVELOPMENT,
        splits=(GoldSplit.DEVELOPMENT,),
        ledger_heads=_ledger_heads(corpus, digest_offset=digest_offset),
    )
    return corpus, policy, evaluator, evaluation_input


def _passing_metrics(policy: KQMPolicy) -> dict[str, float]:
    return {
        name: specification.release_threshold
        for name, specification in policy.metrics.items()
    }


def _point(
    *,
    release_id: str,
    candidate_code_char: str,
    metrics: dict[str, float] | None = None,
    digest_offset: int = 1,
) -> tuple[KQMLongitudinalPoint, KQMPolicy, EvaluationInputIdentity]:
    _, policy, evaluator, evaluation_input = _context(
        digest_offset=digest_offset
    )
    measured = _passing_metrics(policy) if metrics is None else metrics
    projection = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=measured,
    )
    point = KQMLongitudinalPoint.build(
        release_id=release_id,
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        candidate_runtime=_runtime(code_char=candidate_code_char),
        projection=projection,
    )
    return point, policy, evaluation_input


def test_kqm03_point_binds_exact_context_runtime_and_projection() -> None:
    point, policy, evaluation_input = _point(
        release_id="build-a",
        candidate_code_char="2",
    )

    assert point.comparison_context_identity == evaluation_input.input_identity
    assert point.input_identity == evaluation_input.input_identity
    assert point.corpus_identity == evaluation_input.corpus_identity
    assert point.policy_identity == policy.policy_identity
    assert point.candidate_runtime_identity.digest != evaluation_input.input_identity.digest
    assert point.projection_passed is True
    assert point.projection_failures == ()
    point.verify()


def test_kqm03_point_identity_changes_when_candidate_runtime_changes() -> None:
    first, _, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    second, _, _ = _point(
        release_id="build-a",
        candidate_code_char="3",
    )

    assert first.comparison_context_identity == second.comparison_context_identity
    assert first.candidate_runtime_identity != second.candidate_runtime_identity
    assert first.point_identity != second.point_identity


def test_kqm03_comparison_allows_candidate_runtime_change_in_same_context() -> None:
    baseline, policy, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    current_metrics = _passing_metrics(policy)
    current_metrics["evidence_coverage"] += 0.01
    current, _, _ = _point(
        release_id="build-b",
        candidate_code_char="3",
        metrics=current_metrics,
    )

    result = compare_kqm_points(baseline, current, policy=policy)
    by_metric = {delta.metric: delta for delta in result.deltas}

    assert result.regression_free is True
    assert by_metric["evidence_coverage"].direction is KQMDeltaDirection.IMPROVED
    assert by_metric["renderer_fidelity"].direction is KQMDeltaDirection.STABLE
    result.verify()


def test_kqm03_regression_direction_respects_existing_policy() -> None:
    baseline, policy, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    current_metrics = _passing_metrics(policy)
    current_metrics["evidence_coverage"] -= 0.01
    current_metrics["unsupported_conclusion_rate"] += 0.01
    current, _, _ = _point(
        release_id="build-b",
        candidate_code_char="3",
        metrics=current_metrics,
    )

    result = compare_kqm_points(baseline, current, policy=policy)
    by_metric = {delta.metric: delta for delta in result.deltas}

    assert result.regression_free is False
    assert by_metric["evidence_coverage"].direction is KQMDeltaDirection.REGRESSED
    assert (
        by_metric["unsupported_conclusion_rate"].direction
        is KQMDeltaDirection.REGRESSED
    )


def test_kqm03_missing_metric_is_not_silently_comparable_as_pass() -> None:
    baseline, policy, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    current_metrics = _passing_metrics(policy)
    current_metrics.pop("evidence_coverage")
    current, _, _ = _point(
        release_id="build-b",
        candidate_code_char="3",
        metrics=current_metrics,
    )

    result = compare_kqm_points(baseline, current, policy=policy)
    by_metric = {delta.metric: delta for delta in result.deltas}

    assert current.projection_passed is False
    assert result.regression_free is False
    assert by_metric["evidence_coverage"].direction is KQMDeltaDirection.MISSING


def test_kqm03_changed_ledger_head_fails_closed_as_noncomparable() -> None:
    baseline, policy, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
        digest_offset=1,
    )
    current, _, _ = _point(
        release_id="build-b",
        candidate_code_char="3",
        digest_offset=100,
    )

    with pytest.raises(
        EvaluationContractError,
        match="evaluation input identity changed",
    ):
        compare_kqm_points(baseline, current, policy=policy)


def test_kqm03_incomplete_candidate_runtime_fails_closed() -> None:
    _, policy, evaluator, evaluation_input = _context()
    projection = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=_passing_metrics(policy),
    )

    with pytest.raises(
        EvaluationContractError,
        match="candidate runtime identity is incomplete",
    ):
        KQMLongitudinalPoint.build(
            release_id="build-a",
            evaluation_input=evaluation_input,
            policy=policy,
            evaluator=evaluator,
            candidate_runtime=_runtime(
                code_char="2",
                complete=False,
            ),
            projection=projection,
        )


def test_kqm03_point_round_trip_is_content_address_verified() -> None:
    point, _, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )

    restored = KQMLongitudinalPoint.from_dict(point.canonical_dict())

    assert restored == point


def test_kqm03_unknown_persisted_field_fails_closed() -> None:
    point, _, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    value = point.canonical_dict()
    value["unexpected"] = True

    with pytest.raises(
        EvaluationContractError,
        match="fields do not match schema",
    ):
        KQMLongitudinalPoint.from_dict(value)


def test_kqm03_persistent_history_round_trip_and_compare(
    tmp_path: Path,
) -> None:
    baseline, policy, evaluation_input = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    current, _, _ = _point(
        release_id="build-b",
        candidate_code_char="3",
    )
    history = PersistentKQMHistory(
        tmp_path / "kqm.jsonl",
        storage_runtime_identity=_runtime(code_char="4"),
        comparison_context_identity=evaluation_input.input_identity,
        policy_identity=policy.policy_identity,
    )

    history.append(baseline)
    history.append(current)

    assert history.points() == (baseline, current)
    comparison = history.compare(
        "build-a",
        "build-b",
        policy=policy,
    )
    assert comparison.regression_free is True
    assert history.head_digest() != "0" * 64


def test_kqm03_history_rejects_duplicate_release(
    tmp_path: Path,
) -> None:
    point, policy, evaluation_input = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    history = PersistentKQMHistory(
        tmp_path / "kqm.jsonl",
        storage_runtime_identity=_runtime(code_char="4"),
        comparison_context_identity=evaluation_input.input_identity,
        policy_identity=policy.policy_identity,
    )
    history.append(point)

    with pytest.raises(
        EvaluationContractError,
        match="duplicate longitudinal release_id",
    ):
        history.append(point)


def test_kqm03_history_rejects_context_substitution(
    tmp_path: Path,
) -> None:
    point, policy, _ = _point(
        release_id="build-a",
        candidate_code_char="2",
        digest_offset=1,
    )
    _, _, other_input = _point(
        release_id="build-x",
        candidate_code_char="3",
        digest_offset=100,
    )
    history = PersistentKQMHistory(
        tmp_path / "kqm.jsonl",
        storage_runtime_identity=_runtime(code_char="4"),
        comparison_context_identity=other_input.input_identity,
        policy_identity=policy.policy_identity,
    )

    with pytest.raises(
        EvaluationContractError,
        match="evaluation context mismatch",
    ):
        history.append(point)


def test_kqm03_tampered_history_fails_hash_chain_verification(
    tmp_path: Path,
) -> None:
    point, policy, evaluation_input = _point(
        release_id="build-a",
        candidate_code_char="2",
    )
    path = tmp_path / "kqm.jsonl"
    history = PersistentKQMHistory(
        path,
        storage_runtime_identity=_runtime(code_char="4"),
        comparison_context_identity=evaluation_input.input_identity,
        policy_identity=policy.policy_identity,
    )
    history.append(point)
    raw = path.read_text(encoding="utf-8")
    path.write_text(
        raw.replace("build-a", "build-z"),
        encoding="utf-8",
    )

    with pytest.raises(P3ContractError):
        history.points()
