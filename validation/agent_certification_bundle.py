"""Deterministic builder for Production Validation Step 8 agent certification evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from agents.certification import AgentCertificationThresholds, AgentCertifier, contract_sha256
from agents.certification_program import (
    AgentCertificationProgram,
    CertificationProgramEvidence,
    CertificationProgramStatus,
    router_certification_update,
)
from agents.kqm import run_reference_agent_kqm
from agents.reference_fact import REFERENCE_FACT_AGENT_ID, ReferenceFactAgent
from validation.certification_mode import CertificationMode, load_certification_profile
from validation.corpus_review import validate_external_corpus_review
from validation.independent_evaluation import ReviewOutcome

EXTRACTION_CORPUS = Path("data/quality/extraction_gold_v1.json")
EXTRACTION_REVIEW = Path("docs/quality/reviews/extraction_gold_v1_review.json")
EXTRACTION_FREEZE = Path("data/quality/extraction_gold_v1.freeze.json")
TAXONOMY = Path("docs/quality/critical_facts_schema.yaml")
STEP3_REPORT = Path("reports/production_validation/step_03.json")
STEP3_EVIDENCE = Path("factory/production_validation_evidence/step_03.json")
STEP7_REPORT = Path("reports/production_validation/step_07.json")
STEP7_EVIDENCE = Path("factory/production_validation_evidence/step_07.json")
RESERVED_REVIEWERS = frozenset({"system", "automated", "factory", "lukart", "agent"})
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class AgentCertificationBundleError(RuntimeError):
    """Raised when Step 8 cannot be regenerated from current evidence."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentCertificationBundleError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise AgentCertificationBundleError(f"JSON artifact must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_pass_envelope(root: Path, evidence_path: Path, report_path: Path) -> dict[str, object]:
    evidence = _load_json(root / evidence_path)
    report = _load_json(root / report_path)
    if evidence.get("status") != "PASS" or evidence.get("critical_gates_passed") is not True:
        raise AgentCertificationBundleError(f"active evidence is not PASS: {evidence_path}")
    if evidence.get("artifact_path") != report_path.as_posix():
        raise AgentCertificationBundleError(f"artifact path mismatch: {evidence_path}")
    if evidence.get("artifact_sha256") != _sha256(root / report_path):
        raise AgentCertificationBundleError(f"artifact hash mismatch: {evidence_path}")
    if report.get("status") != "PASS":
        raise AgentCertificationBundleError(f"bound report is not PASS: {report_path}")
    return report


def _thresholds(step3: dict[str, object]) -> AgentCertificationThresholds:
    raw = step3.get("thresholds")
    if not isinstance(raw, dict):
        raise AgentCertificationBundleError("Step 3 thresholds are missing")
    return AgentCertificationThresholds(
        min_precision=float(raw["min_precision"]),
        min_recall=float(raw["min_recall"]),
        min_f1=float(raw["min_f1"]),
        min_critical_recall=float(raw["min_critical_recall"]),
        min_provenance_completeness=float(raw["min_provenance_completeness"]),
        max_critical_fact_loss=int(raw["max_critical_fact_loss"]),
        max_case_number_false_positive_rate=float(raw["max_case_number_false_positive_rate"]),
    )


def build_reference_fact_agent_bundle(root: Path, *, validated_sha: str) -> dict[str, object]:
    """Regenerate Step 8 from current measured evidence without touching locked data."""

    if not _GIT_SHA_RE.fullmatch(validated_sha):
        raise AgentCertificationBundleError("validated_sha must be a full lowercase Git SHA")

    profile = load_certification_profile(root, required=True)
    if profile.mode is not CertificationMode.SOLO_MAINTAINER:
        raise AgentCertificationBundleError(
            "current Step 8 builder requires explicit SOLO_MAINTAINER_MODE"
        )

    corpus_path = root / EXTRACTION_CORPUS
    review = _load_json(root / EXTRACTION_REVIEW)
    freeze = _load_json(root / EXTRACTION_FREEZE)
    corpus_sha256 = _sha256(corpus_path)
    validate_external_corpus_review(
        review,
        expected_corpus_id="extraction-gold-v1",
        expected_corpus_sha256=corpus_sha256,
        reserved_reviewer_ids=RESERVED_REVIEWERS,
    )
    expected_freeze = {
        "schema_version": "1.0",
        "corpus_id": "extraction-gold-v1",
        "corpus_sha256": corpus_sha256,
        "status": "FROZEN",
        "reviewer_id": profile.maintainer_id,
        "review_digest": _canonical_digest(review),
    }
    for key, expected in expected_freeze.items():
        if freeze.get(key) != expected:
            raise AgentCertificationBundleError(f"extraction freeze mismatch: {key}")

    step3 = _require_pass_envelope(root, STEP3_EVIDENCE, STEP3_REPORT)
    if step3.get("certification_decision") != "PASS":
        raise AgentCertificationBundleError("Step 3 certification decision is not PASS")
    if step3.get("locked_evaluation_used_for_tuning") is not False:
        raise AgentCertificationBundleError("Step 3 violates locked-use boundary")

    step7 = _require_pass_envelope(root, STEP7_EVIDENCE, STEP7_REPORT)
    checks = step7.get("checks")
    if not isinstance(checks, list) or not checks:
        raise AgentCertificationBundleError("Step 7 checks are missing")
    if any(not isinstance(item, dict) or item.get("status") != "PASS" for item in checks):
        raise AgentCertificationBundleError("Step 7 contains a failed check")

    thresholds = _thresholds(step3)
    measured = run_reference_agent_kqm(corpus_path, root / TAXONOMY, thresholds)
    if measured.locked_split_executed:
        raise AgentCertificationBundleError("Step 8 must not execute locked extraction data")

    agent = ReferenceFactAgent()
    analytical = AgentCertifier(
        thresholds,
        require_independent_review=False,
    ).evaluate(
        agent.contract,
        measured.validation,
        corpus_version=measured.corpus_id,
        split_name="validation",
        external_review=ReviewOutcome.NOT_PERFORMED,
    )
    program = AgentCertificationProgram().evaluate(
        analytical,
        CertificationProgramEvidence(
            validated_sha=validated_sha,
            expected_contract_sha256=contract_sha256(agent.contract),
            engineering_validated=True,
            e2e_suite_passed=True,
            e2e_report_sha256=_sha256(root / STEP7_REPORT),
            independent_review_required=False,
        ),
    )
    if program.status is not CertificationProgramStatus.CERTIFIED:
        raise AgentCertificationBundleError(
            "ReferenceFactAgent did not reach program certification"
        )

    eligibility = router_certification_update(REFERENCE_FACT_AGENT_ID, program)
    if not eligibility:
        raise AgentCertificationBundleError("certified agent did not become router-eligible")

    router_rows = [
        {
            "agent_id": agent_id,
            "agent_version": version,
            "certification_status": status.value,
        }
        for (agent_id, version), status in sorted(eligibility.items())
    ]

    return {
        "schema_version": "1.0",
        "step": 8,
        "status": "PASS",
        "validated_sha": validated_sha,
        "gate_kind": "certification",
        "evidence_kind": "agent_certification_bundle",
        "locked_evaluation_used_for_tuning": False,
        "private_data_committed": False,
        "certification_mode": profile.mode.value,
        "independent_external_review": profile.independent_external_review,
        "benchmark_bundle": {
            "benchmark_id": "reference-fact-extraction-validation-v1",
            "corpus_id": "extraction-gold-v1",
            "corpus_sha256": corpus_sha256,
            "frozen": True,
            "review_mode": profile.mode.value,
            "maintainer_acceptance_decision": review["decision"],
            "maintainer_id": profile.maintainer_id,
            "independent_external_review": profile.independent_external_review,
            "split": "validation",
        },
        "certification_reports": [program.canonical_dict()],
        "router_eligibility": router_rows,
        "source_evidence": [
            STEP3_REPORT.as_posix(),
            STEP7_REPORT.as_posix(),
            EXTRACTION_REVIEW.as_posix(),
            EXTRACTION_FREEZE.as_posix(),
            EXTRACTION_CORPUS.as_posix(),
            "agents/certification.py",
            "agents/certification_program.py",
        ],
        "checks": [
            {"name": "agent_benchmarks_versioned", "status": "PASS"},
            {"name": "certification_decisions_recorded", "status": "PASS"},
            {"name": "router_eligibility_updated", "status": "PASS"},
        ],
    }


def write_bundle(bundle: dict[str, object], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode()).hexdigest()
