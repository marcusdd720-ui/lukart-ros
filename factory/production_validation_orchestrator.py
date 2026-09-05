"""Fail-closed controller for the post-P7 production validation program."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from factory.production_validation_registry import get_program_step, next_program_step
from validation.corpus_review import (
    ExternalCorpusReviewError,
    validate_external_corpus_review,
)
from validation.independent_step_review import (
    IndependentStepReviewError,
    validate_independent_step_review,
)

STATE_PATH = Path("factory/production_validation_state.json")
EVIDENCE_DIR = Path("factory/production_validation_evidence")
EXTRACTION_CORPUS = Path("data/quality/extraction_gold_v1.json")
EXTRACTION_REVIEW = Path("docs/quality/reviews/extraction_gold_v1_review.json")
EXTRACTION_FREEZE = Path("data/quality/extraction_gold_v1.freeze.json")
REASONING_CORPUS_V2 = Path("data/quality/reasoning_gold_v2.json")
REASONING_REVIEW_V2 = Path("docs/quality/reviews/reasoning_gold_v2_review.json")
REASONING_FREEZE_V2 = Path("data/quality/reasoning_gold_v2.freeze.json")
RESERVED_REVIEWERS = frozenset({"system", "automated", "factory", "lukart", "agent"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class GateDecision:
    passed: bool
    code: str
    reason: str


class ProductionValidationError(RuntimeError):
    """Raised when program state or evidence is malformed."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionValidationError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ProductionValidationError(f"JSON artifact must be an object: {path}")
    return value


def initial_state() -> dict[str, object]:
    return {
        "current_step": 1,
        "last_completed_step": 0,
        "status": "READY",
        "last_result": "NOT_RUN",
    }


def load_state(path: Path = STATE_PATH) -> dict[str, object]:
    if not path.exists():
        return initial_state()
    state = load_json(path)
    current = state.get("current_step")
    completed = state.get("last_completed_step")
    if not isinstance(current, int) or not isinstance(completed, int):
        raise ProductionValidationError("program state requires integer step fields")
    get_program_step(current)
    if completed < 0 or completed > current:
        raise ProductionValidationError("program state has inconsistent ordering")
    return state


def write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _review_digest(review: dict[str, object]) -> str:
    encoded = json.dumps(review, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _evaluate_independent_review(
    root: Path,
    *,
    corpus_path: Path,
    review_path: Path,
    corpus_id: str,
    missing_review_reason: str,
) -> GateDecision:
    corpus = root / corpus_path
    review_file = root / review_path
    if not corpus.exists():
        return GateDecision(
            False,
            "CORPUS_REQUIRED",
            f"corpus artifact is missing: {corpus_path}",
        )
    if not review_file.exists():
        return GateDecision(False, "EXTERNAL_REVIEW_REQUIRED", missing_review_reason)

    review = load_json(review_file)
    try:
        validate_external_corpus_review(
            review,
            expected_corpus_id=corpus_id,
            expected_corpus_sha256=sha256_file(corpus),
            reserved_reviewer_ids=RESERVED_REVIEWERS,
        )
    except ExternalCorpusReviewError as exc:
        return GateDecision(False, exc.code, exc.reason)
    return GateDecision(True, "PASS", "independent review accepted; corpus may be frozen")


def evaluate_extraction_review(root: Path) -> GateDecision:
    return _evaluate_independent_review(
        root,
        corpus_path=EXTRACTION_CORPUS,
        review_path=EXTRACTION_REVIEW,
        corpus_id="extraction-gold-v1",
        missing_review_reason="independent extraction corpus review artifact is missing",
    )


def evaluate_reasoning_review(root: Path) -> GateDecision:
    return _evaluate_independent_review(
        root,
        corpus_path=REASONING_CORPUS_V2,
        review_path=REASONING_REVIEW_V2,
        corpus_id="reasoning-gold-v2",
        missing_review_reason="independent reasoning corpus v2 review artifact is missing",
    )


def _freeze_corpus(
    root: Path,
    *,
    corpus_path: Path,
    review_path: Path,
    freeze_path: Path,
    corpus_id: str,
) -> None:
    review = load_json(root / review_path)
    corpus_hash = sha256_file(root / corpus_path)
    manifest = {
        "schema_version": "1.0",
        "corpus_id": corpus_id,
        "corpus_sha256": corpus_hash,
        "status": "FROZEN",
        "reviewer_id": review["reviewer_id"],
        "review_digest": _review_digest(review),
    }
    path = root / freeze_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def freeze_extraction_corpus(root: Path) -> None:
    _freeze_corpus(
        root,
        corpus_path=EXTRACTION_CORPUS,
        review_path=EXTRACTION_REVIEW,
        freeze_path=EXTRACTION_FREEZE,
        corpus_id="extraction-gold-v1",
    )


def freeze_reasoning_corpus(root: Path) -> None:
    _freeze_corpus(
        root,
        corpus_path=REASONING_CORPUS_V2,
        review_path=REASONING_REVIEW_V2,
        freeze_path=REASONING_FREEZE_V2,
        corpus_id="reasoning-gold-v2",
    )


def evidence_path(step_number: int) -> Path:
    return EVIDENCE_DIR / f"step_{step_number:02d}.json"


def _safe_repo_artifact(
    root: Path,
    raw_path: object,
) -> tuple[Path | None, GateDecision | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, GateDecision(
            False,
            "ARTIFACT_PATH_INVALID",
            "artifact_path must be relative",
        )
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, GateDecision(
            False,
            "ARTIFACT_PATH_INVALID",
            "artifact_path escapes repository",
        )
    root_resolved = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None, GateDecision(
            False,
            "ARTIFACT_PATH_INVALID",
            "artifact_path escapes repository",
        )
    if not resolved.is_file():
        return None, GateDecision(
            False,
            "ARTIFACT_REQUIRED",
            "bound validation artifact is missing",
        )
    if resolved.suffix.lower() != ".json":
        return None, GateDecision(
            False,
            "ARTIFACT_FORMAT_INVALID",
            "bound artifact must be JSON",
        )
    return resolved, None


def _validated_checks(
    artifact: dict[str, object],
) -> tuple[dict[str, str] | None, GateDecision | None]:
    raw_checks = artifact.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        return None, GateDecision(
            False,
            "ARTIFACT_CHECKS_REQUIRED",
            "artifact checks are required",
        )
    checks: dict[str, str] = {}
    for item in raw_checks:
        if not isinstance(item, dict):
            return None, GateDecision(
                False,
                "ARTIFACT_CHECK_INVALID",
                "artifact check must be an object",
            )
        name = item.get("name")
        status = item.get("status")
        if not isinstance(name, str) or not name.strip() or not isinstance(status, str):
            return None, GateDecision(
                False,
                "ARTIFACT_CHECK_INVALID",
                "artifact check is malformed",
            )
        if name in checks:
            return None, GateDecision(
                False,
                "ARTIFACT_CHECK_DUPLICATE",
                f"duplicate check: {name}",
            )
        checks[name] = status
    failed = sorted(name for name, status in checks.items() if status != "PASS")
    if failed:
        return None, GateDecision(
            False,
            "ARTIFACT_CHECK_FAILED",
            f"artifact contains non-PASS checks: {', '.join(failed)}",
        )
    return checks, None


def evaluate_generic_evidence(root: Path, step_number: int) -> GateDecision:
    spec = get_program_step(step_number)
    path = root / evidence_path(step_number)
    if not path.exists():
        return GateDecision(
            False,
            "STEP_EVIDENCE_REQUIRED",
            f"validated evidence for step {step_number} is missing",
        )
    evidence = load_json(path)
    if evidence.get("schema_version") != "2.0":
        return GateDecision(
            False,
            "STEP_EVIDENCE_SCHEMA_INVALID",
            "step evidence schema must be 2.0",
        )
    if evidence.get("step") != step_number or evidence.get("status") != "PASS":
        return GateDecision(
            False,
            "STEP_EVIDENCE_INVALID",
            "step evidence does not declare PASS",
        )
    validated_sha = evidence.get("validated_sha")
    if not isinstance(validated_sha, str) or not GIT_SHA_RE.fullmatch(validated_sha):
        return GateDecision(
            False,
            "VALIDATED_SHA_INVALID",
            "validated_sha must be a full Git SHA",
        )
    if evidence.get("gate_kind") != spec.gate_kind.value:
        return GateDecision(False, "GATE_KIND_MISMATCH", "step evidence gate kind mismatch")
    if evidence.get("evidence_kind") != spec.evidence_kind:
        return GateDecision(
            False,
            "EVIDENCE_KIND_MISMATCH",
            "step evidence kind mismatch",
        )
    if evidence.get("critical_gates_passed") is not True:
        return GateDecision(
            False,
            "CRITICAL_GATES_INCOMPLETE",
            "critical gates must be explicit",
        )

    artifact_path, path_decision = _safe_repo_artifact(root, evidence.get("artifact_path"))
    if path_decision is not None:
        return path_decision
    if artifact_path is None:
        raise ProductionValidationError("artifact path validation returned no result")
    if artifact_path == path.resolve():
        return GateDecision(
            False,
            "ARTIFACT_SELF_REFERENCE",
            "step evidence cannot bind to itself",
        )

    expected_digest = evidence.get("artifact_sha256")
    if not isinstance(expected_digest, str) or not SHA256_RE.fullmatch(expected_digest):
        return GateDecision(
            False,
            "ARTIFACT_DIGEST_INVALID",
            "artifact_sha256 must be SHA-256",
        )
    if sha256_file(artifact_path) != expected_digest:
        return GateDecision(
            False,
            "ARTIFACT_HASH_MISMATCH",
            "step evidence is not bound to artifact bytes",
        )

    artifact = load_json(artifact_path)
    required_artifact_fields = {
        "schema_version": "1.0",
        "step": step_number,
        "status": "PASS",
        "validated_sha": validated_sha,
        "gate_kind": spec.gate_kind.value,
        "evidence_kind": spec.evidence_kind,
        "locked_evaluation_used_for_tuning": False,
        "private_data_committed": False,
    }
    for key, expected in required_artifact_fields.items():
        if artifact.get(key) != expected:
            return GateDecision(
                False,
                "ARTIFACT_CONTRACT_MISMATCH",
                f"bound artifact field {key} does not match evidence contract",
            )

    checks, checks_decision = _validated_checks(artifact)
    if checks_decision is not None:
        return checks_decision
    if checks is None:
        raise ProductionValidationError("artifact check validation returned no result")
    missing = sorted(set(spec.required_checks) - set(checks))
    if missing:
        return GateDecision(
            False,
            "REQUIRED_CHECKS_MISSING",
            f"required step checks are missing: {', '.join(missing)}",
        )

    if step_number in {16, 18}:
        raw_artifact_path = evidence.get("artifact_path")
        if not isinstance(raw_artifact_path, str):
            raise ProductionValidationError("validated artifact path must be text")
        try:
            validate_independent_step_review(
                root,
                evidence,
                expected_step=step_number,
                expected_validated_sha=validated_sha,
                expected_artifact_path=raw_artifact_path,
                expected_artifact_sha256=expected_digest,
                reserved_reviewer_ids=RESERVED_REVIEWERS,
            )
        except IndependentStepReviewError as exc:
            return GateDecision(False, exc.code, exc.reason)

    return GateDecision(
        True,
        "PASS",
        f"step {step_number} evidence accepted and artifact verified",
    )


def _validate_freeze_manifest(
    root: Path,
    *,
    corpus_path: Path,
    review_path: Path,
    freeze_path: Path,
    corpus_id: str,
) -> GateDecision:
    corpus = root / corpus_path
    review_file = root / review_path
    freeze_file = root / freeze_path
    if not freeze_file.is_file():
        return GateDecision(
            False,
            "FREEZE_MANIFEST_REQUIRED",
            f"frozen corpus manifest is missing: {freeze_path}",
        )
    review = load_json(review_file)
    freeze = load_json(freeze_file)
    expected = {
        "schema_version": "1.0",
        "corpus_id": corpus_id,
        "corpus_sha256": sha256_file(corpus),
        "status": "FROZEN",
        "reviewer_id": review.get("reviewer_id"),
        "review_digest": _review_digest(review),
    }
    for name, value in expected.items():
        if freeze.get(name) != value:
            return GateDecision(
                False,
                "FREEZE_MANIFEST_MISMATCH",
                f"freeze manifest field {name} is stale or invalid",
            )
    return GateDecision(True, "PASS", f"freeze manifest verified: {freeze_path}")


def _generic_chain_entry(
    root: Path,
    step_number: int,
) -> tuple[dict[str, object] | None, GateDecision | None]:
    envelope = root / evidence_path(step_number)
    evidence = load_json(envelope)
    artifact_path, path_decision = _safe_repo_artifact(root, evidence.get("artifact_path"))
    if path_decision is not None:
        return None, path_decision
    if artifact_path is None:
        raise ProductionValidationError("artifact path validation returned no result")
    return (
        {
            "artifact_sha256": sha256_file(artifact_path),
            "evidence_sha256": sha256_file(envelope),
            "step": step_number,
            "validated_sha": evidence.get("validated_sha"),
        },
        None,
    )


def production_validation_chain_digest(
    root: Path,
) -> tuple[str | None, GateDecision | None]:
    """Re-evaluate and digest the actual evidence chain for Steps 1-19."""

    entries: list[dict[str, object]] = []
    freeze_specs = {
        1: (
            EXTRACTION_CORPUS,
            EXTRACTION_REVIEW,
            EXTRACTION_FREEZE,
            "extraction-gold-v1",
        ),
        5: (
            REASONING_CORPUS_V2,
            REASONING_REVIEW_V2,
            REASONING_FREEZE_V2,
            "reasoning-gold-v2",
        ),
    }
    for step_number in range(1, 20):
        decision = evaluate_step(root, step_number)
        if not decision.passed:
            return None, GateDecision(
                False,
                "PRIOR_STEP_NOT_COMPLETE",
                f"step {step_number} failed revalidation: {decision.code}: {decision.reason}",
            )
        if step_number in freeze_specs:
            corpus_path, review_path, freeze_path, corpus_id = freeze_specs[step_number]
            freeze_decision = _validate_freeze_manifest(
                root,
                corpus_path=corpus_path,
                review_path=review_path,
                freeze_path=freeze_path,
                corpus_id=corpus_id,
            )
            if not freeze_decision.passed:
                return None, GateDecision(
                    False,
                    freeze_decision.code,
                    f"step {step_number}: {freeze_decision.reason}",
                )
            entries.append(
                {
                    "corpus_sha256": sha256_file(root / corpus_path),
                    "freeze_sha256": sha256_file(root / freeze_path),
                    "review_sha256": sha256_file(root / review_path),
                    "step": step_number,
                }
            )
        else:
            entry, entry_decision = _generic_chain_entry(root, step_number)
            if entry_decision is not None:
                return None, entry_decision
            if entry is None:
                raise ProductionValidationError("chain entry validation returned no result")
            entries.append(entry)

    payload = json.dumps(
        {"schema_version": "1.0", "steps": entries},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest(), None


def evaluate_release_candidate(root: Path) -> GateDecision:
    """Issue Step 20 only when the live Steps 1-19 evidence chain still verifies."""

    chain_digest, chain_decision = production_validation_chain_digest(root)
    if chain_decision is not None:
        return chain_decision
    if chain_digest is None:
        raise ProductionValidationError("release chain validation returned no digest")

    decision = evaluate_generic_evidence(root, 20)
    if not decision.passed:
        return decision

    evidence = load_json(root / evidence_path(20))
    artifact_path, path_decision = _safe_repo_artifact(root, evidence.get("artifact_path"))
    if path_decision is not None:
        return path_decision
    if artifact_path is None:
        raise ProductionValidationError("release artifact validation returned no result")
    artifact = load_json(artifact_path)
    if artifact.get("steps_1_19_digest") != chain_digest:
        return GateDecision(
            False,
            "RELEASE_CHAIN_DIGEST_MISMATCH",
            "release candidate is not bound to the current Steps 1-19 evidence chain",
        )
    return GateDecision(
        True,
        "PASS",
        "Step 20 release candidate verified against the complete live evidence chain",
    )


def evaluate_step(root: Path, step_number: int) -> GateDecision:
    if step_number == 1:
        return evaluate_extraction_review(root)
    if step_number == 5:
        return evaluate_reasoning_review(root)
    if step_number == 20:
        return evaluate_release_candidate(root)
    return evaluate_generic_evidence(root, step_number)


def advance_state(state: dict[str, object], step_number: int) -> None:
    following = next_program_step(step_number)
    state["last_completed_step"] = step_number
    state["last_result"] = "PASS"
    state.pop("block_code", None)
    state.pop("block_reason", None)
    if following is None:
        state["current_step"] = step_number
        state["status"] = "COMPLETE"
    else:
        state["current_step"] = following.number
        state["status"] = "READY"


def apply_current_step(root: Path, state_path: Path) -> GateDecision:
    state = load_state(state_path)
    if state.get("status") == "COMPLETE":
        return GateDecision(True, "PROGRAM_COMPLETE", "all 20 steps are complete")
    current = state.get("current_step")
    if not isinstance(current, int):
        raise ProductionValidationError("current_step must be an integer")
    decision = evaluate_step(root, current)
    if decision.passed:
        if current == 1:
            freeze_extraction_corpus(root)
        elif current == 5:
            freeze_reasoning_corpus(root)
        advance_state(state, current)
    else:
        state["status"] = "BLOCKED"
        state["last_result"] = "BLOCKED"
        state["block_code"] = decision.code
        state["block_reason"] = decision.reason
    write_state(state_path, state)
    return decision


def _git_changed() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def publish_changes() -> None:
    """Commit validation state locally; remote publication is PR-only."""

    if not _git_changed():
        return
    paths = [str(STATE_PATH)]
    for freeze_path in (EXTRACTION_FREEZE, REASONING_FREEZE_V2):
        if freeze_path.exists():
            paths.append(str(freeze_path))
    commands = (
        ["git", "add", *paths],
        ["git", "commit", "-m", "chore: advance production validation program"],
    )
    for command in commands:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise ProductionValidationError(f"command failed: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--state-file", type=Path, default=STATE_PATH)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    state = load_state(args.state_file)
    current = state["current_step"]
    if not isinstance(current, int):
        raise ProductionValidationError("current_step must be an integer")
    step = get_program_step(current)
    print(f"PROGRAM_STEP={step.number}")
    print(f"PROGRAM_STEP_NAME={step.name}")
    decision = apply_current_step(args.root, args.state_file)
    print(f"PROGRAM_DECISION={decision.code}")
    print(f"PROGRAM_REASON={decision.reason}")
    if args.apply:
        publish_changes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
