from __future__ import annotations

from pathlib import Path
from typing import cast

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
    KQMPolicy,
    KQMProjection,
    MetricDirection,
    MetricSpec,
)
from core.p3.contracts import RuntimeIdentity
from validation.gold_kqm_v2 import load_gold_corpus_identity, load_kqm_policy

GOLD_PATH = Path("data/quality/post_v1_gold_v1_1.json")
MANIFEST_PATH = Path("data/quality/post_v1_gold_v1_1.manifest.json")
KQM_PATH = Path("config/post_hardcore_kqm_v2.json")


def _runtime(*, provider: str = "provider-a@1") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="evaluation.v2",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=(provider,),
        provider_inventory_declared=True,
    )


def _evaluator(*, provider: str = "provider-a@1") -> EvaluatorIdentity:
    return EvaluatorIdentity.build(
        evaluator_id="lukart-kqm-reference",
        evaluator_version="2.0.0",
        code_sha="d" * 40,
        runtime_identity=_runtime(provider=provider),
    )


def _heads(
    corpus: GoldCorpusIdentity,
    split: GoldSplit,
    *,
    digest_char: str = "e",
) -> tuple[CaseLedgerHead, ...]:
    address = ContentAddress(algorithm=DigestAlgorithm.SHA256, digest=digest_char * 64)
    return tuple(
        CaseLedgerHead(case_id=CaseId(case_id), head_event_id=address)
        for case_id in corpus.split_case_ids[split]
    )


def _passing_metrics(policy: KQMPolicy) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, spec in policy.metrics.items():
        result[name] = spec.release_threshold
    return result


def test_phx02_current_gold_assets_have_deterministic_verified_identity() -> None:
    first = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    second = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)

    assert first == second
    assert first.corpus_id == "post-v1-gold-v1.1"
    assert first.corpus_version == "1.1.0"
    assert len(first.case_ids) == 15
    assert len(first.split_case_ids[GoldSplit.DEVELOPMENT]) == 5
    assert len(first.split_case_ids[GoldSplit.VALIDATION]) == 5
    assert len(first.split_case_ids[GoldSplit.LOCKED_EVALUATION]) == 5
    assert first.review_status == "candidate_pending_independent_freeze"
    assert first.reviewer is None
    assert first.locked_evaluation_policy == "certification_only_no_tuning"
    assert first.source_digest != first.canonical_content_digest
    assert str(first.corpus_identity).startswith("sha256:")


def test_phx02_kqm_v2_policy_is_versioned_content_addressed_and_immutable() -> None:
    policy = load_kqm_policy(KQM_PATH)

    assert policy.version == "2.0.0"
    assert policy.missing_metric == "FAIL"
    assert policy.threshold_relaxation_requires_versioned_policy_change is True
    assert policy.evaluator_may_mutate_product_state is False
    assert len(policy.metrics) == 9
    assert policy.metrics["evidence_coverage"].direction is MetricDirection.MIN
    assert policy.metrics["unsupported_conclusion_rate"].direction is MetricDirection.MAX

    with pytest.raises(TypeError):
        cast(dict[str, MetricSpec], policy.metrics)["new_metric"] = MetricSpec(
            direction=MetricDirection.MIN,
            warning_threshold=1.0,
            release_threshold=1.0,
        )


def test_phx02_evaluation_input_is_bound_to_exact_case_ledger_heads() -> None:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    heads = _heads(corpus, GoldSplit.DEVELOPMENT)

    baseline = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.DEVELOPMENT,
        splits=(GoldSplit.DEVELOPMENT,),
        ledger_heads=heads,
    )
    changed_heads = list(heads)
    changed_heads[0] = CaseLedgerHead(
        case_id=changed_heads[0].case_id,
        head_event_id=ContentAddress(
            algorithm=DigestAlgorithm.SHA256,
            digest="f" * 64,
        ),
    )
    changed = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.DEVELOPMENT,
        splits=(GoldSplit.DEVELOPMENT,),
        ledger_heads=changed_heads,
    )

    assert baseline.input_identity != changed.input_identity
    assert baseline.selected_case_ids == corpus.split_case_ids[GoldSplit.DEVELOPMENT]


def test_phx02_locked_evaluation_requires_certification_purpose() -> None:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    locked_heads = _heads(corpus, GoldSplit.LOCKED_EVALUATION)

    with pytest.raises(EvaluationContractError, match="only be selected for certification"):
        EvaluationInputIdentity.build(
            corpus=corpus,
            policy=policy,
            evaluator=evaluator,
            purpose=EvaluationPurpose.VALIDATION,
            splits=(GoldSplit.LOCKED_EVALUATION,),
            ledger_heads=locked_heads,
        )

    certification = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.CERTIFICATION,
        splits=(GoldSplit.LOCKED_EVALUATION,),
        ledger_heads=locked_heads,
    )
    assert certification.purpose is EvaluationPurpose.CERTIFICATION
    assert certification.splits == (GoldSplit.LOCKED_EVALUATION,)


def test_phx02_evaluator_identity_changes_with_exact_runtime_provider_identity() -> None:
    first = _evaluator(provider="provider-a@1")
    second = _evaluator(provider="provider-b@7")

    assert first.runtime_identity_digest != second.runtime_identity_digest
    assert first.evaluator_identity != second.evaluator_identity


def test_phx02_kqm_projection_is_deterministic_and_missing_metric_fails_closed() -> None:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    evaluation_input = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.DEVELOPMENT,
        splits=(GoldSplit.DEVELOPMENT,),
        ledger_heads=_heads(corpus, GoldSplit.DEVELOPMENT),
    )
    metrics = _passing_metrics(policy)

    passed = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=metrics,
    )
    repeated = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=metrics,
    )
    missing = dict(metrics)
    missing.pop("evidence_coverage")
    failed = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=missing,
    )

    assert passed.passed is True
    assert passed.failures == ()
    assert passed == repeated
    assert failed.passed is False
    assert "missing metric: evidence_coverage" in failed.failures
    assert failed.projection_identity != passed.projection_identity


def test_phx02_policy_content_change_creates_new_identity() -> None:
    original = load_kqm_policy(KQM_PATH)
    value = original.canonical_body()
    value["version"] = "2.0.1"
    value["policy"] = {
        "missing_metric": value.pop("missing_metric"),
        "threshold_relaxation_requires_versioned_policy_change": value.pop(
            "threshold_relaxation_requires_versioned_policy_change"
        ),
        "evaluator_may_mutate_product_state": value.pop("evaluator_may_mutate_product_state"),
    }
    value.pop("canonicalization_profile")
    changed = KQMPolicy.build(value)

    assert changed.version == "2.0.1"
    assert changed.policy_identity != original.policy_identity
