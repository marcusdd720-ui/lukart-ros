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

STATE_PATH = Path("factory/production_validation_state.json")
EVIDENCE_DIR = Path("factory/production_validation_evidence")
EXTRACTION_CORPUS = Path("data/quality/extraction_gold_v1.json")
EXTRACTION_REVIEW = Path("docs/quality/reviews/extraction_gold_v1_review.json")
EXTRACTION_FREEZE = Path("data/quality/extraction_gold_v1.freeze.json")
RESERVED_REVIEWERS = {"system", "automated", "factory", "lukart", "agent"}
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


def _reviewer_is_independent(review: dict[str, object]) -> bool:
    reviewer = review.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        return False
    normalized = reviewer.strip().lower()
    if normalized in RESERVED_REVIEWERS:
        return False
    return review.get("reviewer_independent") is True


def evaluate_extraction_review(root: Path) -> GateDecision:
    corpus_path = root / EXTRACTION_CORPUS
    review_path = root / EXTRACTION_REVIEW
    if not review_path.exists():
        return GateDecision(
            False,
            "EXTERNAL_REVIEW_REQUIRED",
            "independent extraction corpus review artifact is missing",
        )
    review = load_json(review_path)
    if review.get("corpus_id") != "extraction-gold-v1":
        return GateDecision(False, "REVIEW_CORPUS_MISMATCH", "review corpus id mismatch")
    expected_hash = sha256_file(corpus_path)
    if review.get("corpus_sha256") != expected_hash:
        return GateDecision(False, "REVIEW_HASH_MISMATCH", "review is not bound to corpus bytes")
    if not _reviewer_is_independent(review):
        return GateDecision(False, "REVIEW_NOT_INDEPENDENT", "independent reviewer required")
    required = {
        "decision": "APPROVED",
        "annotation_review": "APPROVED",
        "criticality_review": "APPROVED",
        "freeze_approved": True,
    }
    for key, value in required.items():
        if review.get(key) != value:
            return GateDecision(False, "REVIEW_NOT_APPROVED", f"review field {key} not approved")
    iaa_required = review.get("iaa_required")
    iaa_status = review.get("iaa_status")
    if iaa_required is True and iaa_status != "PASS":
        return GateDecision(False, "IAA_REQUIRED", "required inter-annotator agreement not passed")
    return GateDecision(True, "PASS", "independent review accepted; corpus may be frozen")


def freeze_extraction_corpus(root: Path) -> None:
    review = load_json(root / EXTRACTION_REVIEW)
    corpus_hash = sha256_file(root / EXTRACTION_CORPUS)
    manifest = {
        "schema_version": "1.0",
        "corpus_id": "extraction-gold-v1",
        "corpus_sha256": corpus_hash,
        "status": "FROZEN",
        "reviewer_id": review["reviewer_id"],
        "review_digest": hashlib.sha256(
            json.dumps(review, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    path = root / EXTRACTION_FREEZE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence_path(step_number: int) -> Path:
    return EVIDENCE_DIR / f"step_{step_number:02d}.json"


def evaluate_generic_evidence(root: Path, step_number: int) -> GateDecision:
    path = root / evidence_path(step_number)
    if not path.exists():
        return GateDecision(
            False,
            "STEP_EVIDENCE_REQUIRED",
            f"validated evidence for step {step_number} is missing",
        )
    evidence = load_json(path)
    if evidence.get("step") != step_number or evidence.get("status") != "PASS":
        return GateDecision(False, "STEP_EVIDENCE_INVALID", "step evidence does not declare PASS")
    validated_sha = evidence.get("validated_sha")
    if not isinstance(validated_sha, str) or not GIT_SHA_RE.fullmatch(validated_sha):
        return GateDecision(False, "VALIDATED_SHA_INVALID", "validated_sha must be a full Git SHA")
    digest = evidence.get("evidence_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        return GateDecision(False, "EVIDENCE_DIGEST_INVALID", "evidence_sha256 must be SHA-256")
    if evidence.get("critical_gates_passed") is not True:
        return GateDecision(False, "CRITICAL_GATES_INCOMPLETE", "critical gates must be explicit")
    return GateDecision(True, "PASS", f"step {step_number} evidence accepted")


def evaluate_step(root: Path, step_number: int) -> GateDecision:
    if step_number == 1:
        return evaluate_extraction_review(root)
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
    if not _git_changed():
        return
    commands = (
        ["git", "add", str(STATE_PATH), str(EXTRACTION_FREEZE)],
        ["git", "commit", "-m", "chore: advance production validation program"],
        ["git", "push", "origin", "HEAD:main"],
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
