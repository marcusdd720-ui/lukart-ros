from __future__ import annotations

import ast
import hashlib
import json
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
)
from core.p3.contracts import RuntimeIdentity, canonical_json
from validation.gold_kqm_v2 import load_gold_corpus_identity, load_kqm_policy

GOLD_PATH = Path("data/quality/post_v1_gold_v1_1.json")
MANIFEST_PATH = Path("data/quality/post_v1_gold_v1_1.manifest.json")
KQM_PATH = Path("config/post_hardcore_kqm_v2.json")
LOADER_PATH = Path("validation/gold_kqm_v2.py")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="evaluation.v2",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        provider_inventory_declared=True,
    )


def _evaluator() -> EvaluatorIdentity:
    return EvaluatorIdentity.build(
        evaluator_id="lukart-kqm-reference",
        evaluator_version="2.0.0",
        code_sha="d" * 40,
        runtime_identity=_runtime(),
    )


def _build_gold(corpus: dict[str, object], manifest: dict[str, object]) -> GoldCorpusIdentity:
    raw = (json.dumps(corpus, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest = dict(manifest)
    manifest["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
    return GoldCorpusIdentity.build(
        corpus=corpus,
        manifest=manifest,
        source_digest=hashlib.sha256(raw).hexdigest(),
    )


def _development_input() -> tuple[EvaluationInputIdentity, KQMPolicy, EvaluatorIdentity]:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    address = ContentAddress(algorithm=DigestAlgorithm.SHA256, digest="e" * 64)
    heads = tuple(
        CaseLedgerHead(case_id=CaseId(case_id), head_event_id=address)
        for case_id in corpus.split_case_ids[GoldSplit.DEVELOPMENT]
    )
    evaluation_input = EvaluationInputIdentity.build(
        corpus=corpus,
        policy=policy,
        evaluator=evaluator,
        purpose=EvaluationPurpose.DEVELOPMENT,
        splits=(GoldSplit.DEVELOPMENT,),
        ledger_heads=heads,
    )
    return evaluation_input, policy, evaluator


def test_phx02_raw_corpus_tamper_fails_before_identity_acceptance(tmp_path) -> None:
    corpus_bytes = GOLD_PATH.read_bytes().replace(b"120 PLN", b"999 PLN", 1)
    corpus_path = tmp_path / "gold.json"
    manifest_path = tmp_path / "manifest.json"
    corpus_path.write_bytes(corpus_bytes)
    manifest_path.write_bytes(MANIFEST_PATH.read_bytes())

    with pytest.raises(EvaluationContractError, match="raw-file digest mismatch"):
        load_gold_corpus_identity(corpus_path, manifest_path)


def test_phx02_unknown_gold_source_schemas_fail_closed() -> None:
    corpus = _json(GOLD_PATH)
    manifest = _json(MANIFEST_PATH)
    corpus["schema"] = "lukart.gold-corpus.v999"
    with pytest.raises(EvaluationContractError, match="unsupported Gold corpus schema"):
        _build_gold(corpus, manifest)

    corpus = _json(GOLD_PATH)
    manifest = _json(MANIFEST_PATH)
    manifest["schema"] = "lukart.corpus-manifest.v999"
    with pytest.raises(EvaluationContractError, match="unsupported Gold manifest schema"):
        _build_gold(corpus, manifest)


def test_phx02_duplicate_case_and_split_count_mismatch_fail_closed() -> None:
    corpus = _json(GOLD_PATH)
    manifest = _json(MANIFEST_PATH)
    cases = cast(list[dict[str, object]], corpus["cases"])
    cases[1]["case_id"] = cases[0]["case_id"]
    with pytest.raises(EvaluationContractError, match="duplicate Gold case_id"):
        _build_gold(corpus, manifest)

    corpus = _json(GOLD_PATH)
    manifest = _json(MANIFEST_PATH)
    splits = cast(dict[str, object], manifest["splits"])
    splits["development"] = 6
    with pytest.raises(EvaluationContractError, match="split count mismatch"):
        _build_gold(corpus, manifest)


def test_phx02_text_cannot_self_certify_independent_freeze() -> None:
    corpus = _json(GOLD_PATH)
    manifest = _json(MANIFEST_PATH)
    manifest["review_status"] = "independently_frozen"
    manifest["reviewer"] = "self-asserted-reviewer"

    with pytest.raises(EvaluationContractError, match="cannot claim independent freeze"):
        _build_gold(corpus, manifest)

    assert not hasattr(GoldCorpusIdentity, "freeze")
    assert not hasattr(GoldCorpusIdentity, "certify")


def test_phx02_unknown_identity_schema_profile_and_digest_algorithm_fail_closed() -> None:
    identity = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    raw = cast(dict[str, object], json.loads(canonical_json(identity.canonical_dict())))

    unknown_schema = dict(raw)
    unknown_schema["schema"] = "lukart.gold-corpus-identity.v999"
    with pytest.raises(EvaluationContractError, match="unsupported Gold identity schema"):
        GoldCorpusIdentity.from_dict(unknown_schema)

    unknown_profile = dict(raw)
    unknown_profile["canonicalization_profile"] = "future-json"
    with pytest.raises(EvaluationContractError, match="unsupported canonicalization profile"):
        GoldCorpusIdentity.from_dict(unknown_profile)

    unknown_algorithm = dict(raw)
    source = cast(dict[str, object], unknown_algorithm["source_digest"])
    unknown_algorithm["source_digest"] = {**source, "algorithm": "future-hash"}
    with pytest.raises(EvaluationContractError, match="unsupported digest algorithm"):
        GoldCorpusIdentity.from_dict(unknown_algorithm)


def test_phx02_gold_identity_tamper_is_rejected_offline() -> None:
    identity = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    raw = cast(dict[str, object], json.loads(canonical_json(identity.canonical_dict())))
    raw["privacy"] = "tampered"

    with pytest.raises(EvaluationContractError, match="content-address mismatch"):
        GoldCorpusIdentity.from_dict(raw)


def test_phx02_nonfinite_and_invalid_kqm_policy_values_fail_closed() -> None:
    base = _json(KQM_PATH)
    metrics = cast(dict[str, dict[str, object]], base["metrics"])
    metrics["evidence_coverage"]["release_threshold"] = float("nan")
    with pytest.raises(EvaluationContractError, match="must be finite"):
        KQMPolicy.build(base)

    base = _json(KQM_PATH)
    metrics = cast(dict[str, dict[str, object]], base["metrics"])
    metrics["evidence_coverage"]["direction"] = "sideways"
    with pytest.raises(EvaluationContractError, match="unsupported metric direction"):
        KQMPolicy.build(base)

    base = _json(KQM_PATH)
    policy_controls = cast(dict[str, object], base["policy"])
    policy_controls["evaluator_may_mutate_product_state"] = True
    with pytest.raises(EvaluationContractError, match="cannot mutate Product state"):
        KQMPolicy.build(base)


def test_phx02_kqm_policy_rejects_malformed_boolean_controls() -> None:
    base = _json(KQM_PATH)
    policy_controls = cast(dict[str, object], base["policy"])
    policy_controls["threshold_relaxation_requires_versioned_policy_change"] = "false"

    with pytest.raises(EvaluationContractError, match="must be boolean"):
        KQMPolicy.build(base)


def test_phx02_nonfinite_or_unexpected_measurement_fails_closed() -> None:
    evaluation_input, policy, evaluator = _development_input()
    metrics = {name: spec.release_threshold for name, spec in policy.metrics.items()}
    metrics["evidence_coverage"] = float("inf")
    with pytest.raises(EvaluationContractError, match="must be finite"):
        KQMProjection.build(
            evaluation_input=evaluation_input,
            policy=policy,
            evaluator=evaluator,
            metrics=metrics,
        )

    metrics = {name: spec.release_threshold for name, spec in policy.metrics.items()}
    metrics["unregistered_metric"] = 1.0
    with pytest.raises(EvaluationContractError, match="unexpected KQM metrics"):
        KQMProjection.build(
            evaluation_input=evaluation_input,
            policy=policy,
            evaluator=evaluator,
            metrics=metrics,
        )


def test_phx02_projection_tamper_is_rejected_offline() -> None:
    evaluation_input, policy, evaluator = _development_input()
    metrics = {name: spec.release_threshold for name, spec in policy.metrics.items()}
    projection = KQMProjection.build(
        evaluation_input=evaluation_input,
        policy=policy,
        evaluator=evaluator,
        metrics=metrics,
    )
    raw = cast(dict[str, object], json.loads(canonical_json(projection.canonical_dict())))
    raw_metrics = cast(dict[str, object], raw["metrics"])
    raw_metrics["epistemic_accuracy"] = 0.0

    with pytest.raises(EvaluationContractError, match="content-address mismatch"):
        KQMProjection.from_dict(raw)


def test_phx02_locked_split_cannot_be_smuggled_into_non_certification() -> None:
    corpus = load_gold_corpus_identity(GOLD_PATH, MANIFEST_PATH)
    policy = load_kqm_policy(KQM_PATH)
    evaluator = _evaluator()
    address = ContentAddress(algorithm=DigestAlgorithm.SHA256, digest="e" * 64)
    heads = tuple(
        CaseLedgerHead(case_id=CaseId(case_id), head_event_id=address)
        for case_id in corpus.split_case_ids[GoldSplit.LOCKED_EVALUATION]
    )

    for purpose in (EvaluationPurpose.DEVELOPMENT, EvaluationPurpose.VALIDATION):
        with pytest.raises(EvaluationContractError, match="only be selected for certification"):
            EvaluationInputIdentity.build(
                corpus=corpus,
                policy=policy,
                evaluator=evaluator,
                purpose=purpose,
                splits=(GoldSplit.LOCKED_EVALUATION,),
                ledger_heads=heads,
            )


def test_phx02_read_only_loader_has_no_canonical_ledger_write_path() -> None:
    source = LOADER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(LOADER_PATH))

    assert "CanonicalCaseLedger" not in source
    forbidden_calls = {"append", "append_event", "publish_revision"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called.isdisjoint(forbidden_calls)
