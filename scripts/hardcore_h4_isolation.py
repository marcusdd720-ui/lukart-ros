from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from core.enterprise import (
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    ProcessIsolationExecutor,
)
from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
WORKER_MODULE = "core.enterprise._worker_fixture"


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _policy(*functions: str) -> IsolationPolicy:
    return IsolationPolicy(
        timeout_seconds=3.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=tuple(f"{WORKER_MODULE}:{name}" for name in functions),
        process_spawn_allowed=False,
        native_ffi_allowed=False,
        workspace_write_only=True,
    )


def _task(function: str, payload: dict[str, object]) -> IsolatedTask:
    return IsolatedTask(module=WORKER_MODULE, function=function, payload=payload)


def _require_denied(
    executor: ProcessIsolationExecutor,
    function: str,
    payload: dict[str, object],
    marker: str,
) -> dict[str, object]:
    try:
        executor.run(_task(function, payload))
    except IsolatedExecutionError as exc:
        if marker not in str(exc):
            raise RuntimeError(f"unexpected H4 denial reason for {function}: {exc}") from exc
        return {"denied": True, "reason_class": marker}
    raise RuntimeError(f"H4 capability unexpectedly allowed: {function}")


def build_h4_evidence(candidate_sha: str, runner_os: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if head != candidate:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    policy_document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    h4 = policy_document.get("h4_capability_isolation")
    if not isinstance(h4, dict):
        raise RuntimeError("H4 capability-isolation policy is missing")
    required_contract = {
        "python_audit_hook_capability_guard": True,
        "filesystem_mode": "explicit-read-roots-workspace-write-only",
        "deny_symlink_creation": True,
        "deny_process_spawn_by_default": True,
        "deny_native_ffi_by_default": True,
        "deny_network_when_policy_denies": True,
        "sanitized_environment": True,
        "hard_timeout_kill": True,
        "unknown_capability": "FAIL",
        "kernel_or_container_sandbox_claimed": False,
    }
    for key, expected in required_contract.items():
        if h4.get(key) != expected:
            raise RuntimeError(f"H4 policy mismatch for {key}: {h4.get(key)!r} != {expected!r}")

    functions = (
        "echo",
        "environment_snapshot",
        "network_probe",
        "filesystem_read",
        "process_spawn_probe",
        "native_ffi_probe",
    )
    executor = ProcessIsolationExecutor(_policy(*functions))

    control_result = executor.run(_task("echo", {"evidence": "h4"}))
    controls = asdict(control_result.controls)
    if controls["kernel_sandbox"] is not False or controls["audit_hook_enforced"] is not True:
        raise RuntimeError("H4 isolation-control claim boundary is invalid")

    os.environ["LUKART_H4_EVIDENCE_SECRET"] = "must-not-cross"
    try:
        environment = executor.run(
            _task("environment_snapshot", {"key": "LUKART_H4_EVIDENCE_SECRET"})
        )
    finally:
        os.environ.pop("LUKART_H4_EVIDENCE_SECRET", None)
    if environment.output.get("value") is not None:
        raise RuntimeError("H4 sanitized-environment boundary leaked a secret")

    network = executor.run(_task("network_probe", {}))
    if network.output.get("network") != "denied":
        raise RuntimeError("H4 network capability was not denied")

    with tempfile.TemporaryDirectory(prefix="lukart-h4-parent-") as directory:
        outside = Path(directory) / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        filesystem_denial = _require_denied(
            executor,
            "filesystem_read",
            {"path": str(outside)},
            "filesystem read denied",
        )

    process_denial = _require_denied(
        executor,
        "process_spawn_probe",
        {},
        "process spawn denied",
    )
    ffi_denial = _require_denied(
        executor,
        "native_ffi_probe",
        {},
        "native FFI denied",
    )

    evidence_body: dict[str, object] = {
        "schema": "lukart.hardcore.h4-capability-isolation-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "runner_os": runner_os,
        "policy_digest": content_digest(h4),
        "controls": controls,
        "adversarial_denials": {
            "environment_secret_leak": {"denied": True},
            "network": {"denied": True},
            "filesystem_external_read": filesystem_denial,
            "process_spawn": process_denial,
            "native_ffi": ffi_denial,
        },
        "claim_boundary": {
            "kernel_or_container_sandbox": False,
            "control_class": "python-process-capability-boundary",
        },
        "state": "CONTROL_PASS",
    }
    evidence_body["evidence_digest"] = content_digest(evidence_body)
    return evidence_body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate H4 execution-boundary and capability-isolation controls"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--runner-os", default="unknown")
    parser.add_argument(
        "--output",
        default="build/hardcore/h4-capability-isolation.json",
    )
    args = parser.parse_args()

    evidence = build_h4_evidence(args.candidate_sha, args.runner_os)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H4_CAPABILITY_ISOLATION=PASS")
    print(f"H4_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H4_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H4_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
