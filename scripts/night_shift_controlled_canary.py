#!/usr/bin/env python
"""Run the V2-07 local-only controlled mutation canary."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from time import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.night_shift.canary import run_controlled_canary
from core.night_shift.contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
)
from core.night_shift.failure_gate import (
    load_failure_report,
    load_required_failure_scenarios,
)
from core.night_shift.promotion import quorum_from_bundle
from core.night_shift.verification import (
    VerificationBundle,
    VerificationEvidence,
    VerificationGate,
    load_required_verification_gates,
    load_verification_max_age_seconds,
)
from core.p3.contracts import content_digest

POLICY_PATH = REPO_ROOT / "docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml"
EVIDENCE_PATH = (
    REPO_ROOT / "docs/execution_profiles/NIGHT_SHIFT_FAILURE_EVIDENCE_V1.yaml"
)
QUORUM_PROFILE = (
    REPO_ROOT / "docs/execution_profiles/NIGHT_SHIFT_VERIFICATION_QUORUM_V1.yaml"
)


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> int:
    now_epoch = int(time())
    required = load_required_failure_scenarios(POLICY_PATH)
    quorum_gates = load_required_verification_gates(QUORUM_PROFILE)
    quorum_max_age = load_verification_max_age_seconds(QUORUM_PROFILE)
    failure_report = load_failure_report(EVIDENCE_PATH)
    failure_report.require_passed(required_scenarios=required)

    with tempfile.TemporaryDirectory(prefix="night-shift-canary-") as temp_dir:
        root = Path(temp_dir)
        repo = root / "synthetic-repo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        _git(repo, "config", "user.name", "Night Shift Canary")
        synthetic_email = "night-shift-canary" + chr(64) + "example.test"
        _git(repo, "config", "user.email", synthetic_email)
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "README.md").write_text("baseline\n", encoding="utf-8")
        _git(repo, "add", "README.md")
        _git(repo, "commit", "-m", "baseline")
        sha = _git(repo, "rev-parse", "HEAD")

        policy_text = POLICY_PATH.read_text(encoding="utf-8")
        policy = PolicyRef(
            "night-shift-policy",
            "v2",
            content_digest({"policy_text": policy_text}),
        )
        state = LiveStateSnapshot(
            snapshot_id=f"canary-{sha[:12]}",
            repository="synthetic/night-shift-canary",
            branch="main",
            base_sha=sha,
            head_sha=sha,
            observed_at_epoch=now_epoch,
            expires_at_epoch=now_epoch + 900,
            evidence_refs=(f"git:synthetic:{sha}",),
        )
        task = TaskCapsule(
            task_id="v207-controlled-canary",
            repository=state.repository,
            state_snapshot_digest=state.digest(),
            policy_digest=policy.policy_digest,
            objective="prove isolated local mutation and rollback",
            risk_class=RiskClass.R0,
            allowed_paths=("README.md",),
            forbidden_paths=(".github/**",),
            acceptance_checks=("controlled-canary",),
            max_files_changed=1,
            max_lines_changed=10,
        )
        envelope = AutonomyEnvelope(
            envelope_id="v207-local-only",
            issued_at_epoch=now_epoch,
            expires_at_epoch=now_epoch + 900,
            repositories=(state.repository,),
            allowed_risk_classes=(RiskClass.R0,),
            max_tasks=1,
            promotion_mode=PromotionMode.AUTO,
        )
        builder_identity = "canary-builder"
        reviewer_identity = "canary-reviewer"
        verification_evidence = tuple(
            VerificationEvidence(
                gate=gate,
                passed=True,
                subject_sha=state.head_sha,
                task_capsule_digest=task.digest(),
                producer_identity=(
                    reviewer_identity
                    if gate is VerificationGate.INDEPENDENT_REVIEW
                    else builder_identity
                ),
                observed_at_epoch=now_epoch,
                evidence_digest=content_digest(
                    {"gate": gate.value, "result": "PASS", "task": task.digest()}
                ),
                evidence_refs=(f"canary:{gate.value}:pass",),
            )
            for gate in quorum_gates
        )
        quorum = quorum_from_bundle(
            VerificationBundle(
                subject_sha=state.head_sha,
                task_capsule_digest=task.digest(),
                builder_identity=builder_identity,
                reviewer_identity=reviewer_identity,
                evidence=verification_evidence,
            ),
            now_epoch=now_epoch,
            max_evidence_age_seconds=quorum_max_age,
        )
        result = run_controlled_canary(
            repository=repo,
            worktree_root=root / "worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=quorum,
            failure_report=failure_report,
            required_failure_scenarios=required,
            target_path="README.md",
            replacement_text="controlled canary mutation\n",
            now_epoch=now_epoch,
        )

        payload = {
            "mode": "CONTROLLED_LOCAL_CANARY",
            "task_id": result.task_id,
            "input_sha": result.input_sha,
            "output_sha": result.output_sha,
            "promotion_state": result.promotion_state.value,
            "receipt_digest": result.receipt_digest,
            "rollback_verified": result.rollback_verified,
            "published": result.published,
            "failure_scenarios": list(required),
        }
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
