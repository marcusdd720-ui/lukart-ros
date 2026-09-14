from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
CODEOWNERS_PATH = ROOT / ".github" / "CODEOWNERS"
GOVERNANCE_WORKFLOW = WORKFLOWS_DIR / "repository-governance-integrity.yml"
_ACTION_REF = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _workflow_document(path: Path) -> Mapping[str, object]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"workflow parse failed: {path.relative_to(ROOT)}: {exc}") from exc
    return _mapping(payload, label=f"workflow {path.relative_to(ROOT)}")


def _step_uses(job: Mapping[str, object]) -> tuple[str, ...]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return ()
    references: list[str] = []
    for step in steps:
        if isinstance(step, Mapping):
            uses = step.get("uses")
            if isinstance(uses, str):
                references.append(uses)
    return tuple(references)


def _step_runs(job: Mapping[str, object]) -> tuple[str, ...]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return ()
    commands: list[str] = []
    for step in steps:
        if isinstance(step, Mapping):
            run = step.get("run")
            if isinstance(run, str):
                commands.append(run)
    return tuple(commands)


def _runs_python_module(runs: tuple[str, ...], module: str) -> bool:
    pattern = re.compile(
        rf"(?:^|[;&|\n]\s*|\s)python(?:3)?\s+-m\s+{re.escape(module)}(?:\s|$)"
    )
    return any(pattern.search(run) is not None for run in runs)


def _allows_write(scope: str, uses: tuple[str, ...], runs: tuple[str, ...]) -> bool:
    if scope == "security-events":
        return any(ref.startswith("github/codeql-action/") for ref in uses)
    if scope in {"id-token", "attestations"}:
        oidc_consumers = (
            "actions/attest@",
            "actions/attest-",
            "sigstore/",
            "google-github-actions/auth@",
            "aws-actions/configure-aws-credentials@",
            "azure/login@",
        )
        return any(any(ref.startswith(prefix) for prefix in oidc_consumers) for ref in uses)
    if scope == "contents":
        release_mutations = ("gh release create", "gh release upload", "gh release edit")
        if any(any(command in run for command in release_mutations) for run in runs):
            return True
        return _runs_python_module(runs, "factory.stage_orchestrator")
    if scope == "actions":
        return _runs_python_module(runs, "factory.stage_orchestrator")
    if scope == "pull-requests":
        return _runs_python_module(runs, "factory.closure_preparation")
    return False


def validate_workflow_permissions(
    workflow_path: str,
    workflow: Mapping[str, object],
) -> dict[str, object]:
    permissions = _mapping(workflow.get("permissions"), label=f"{workflow_path}.permissions")
    if permissions.get("contents") != "read":
        raise RuntimeError(f"workflow permission drift: {workflow_path} must default contents=read")

    top_level_writes = sorted(
        str(scope) for scope, level in permissions.items() if level == "write"
    )
    if top_level_writes:
        raise RuntimeError(
            "workflow permission drift: top-level write permissions are forbidden: "
            f"{workflow_path}: {top_level_writes}"
        )
    for scope, level in permissions.items():
        if level not in {"read", "none"}:
            raise RuntimeError(
                f"workflow permission drift: unsupported top-level permission "
                f"{workflow_path}:{scope}={level!r}"
            )

    jobs = _mapping(workflow.get("jobs"), label=f"{workflow_path}.jobs")
    job_writes: list[str] = []
    for job_id, raw_job in jobs.items():
        job = _mapping(raw_job, label=f"{workflow_path}.jobs.{job_id}")
        raw_permissions = job.get("permissions")
        if raw_permissions is None:
            continue
        job_permissions = _mapping(
            raw_permissions,
            label=f"{workflow_path}.jobs.{job_id}.permissions",
        )
        uses = _step_uses(job)
        runs = _step_runs(job)
        for scope, level in job_permissions.items():
            if level not in {"read", "write", "none"}:
                raise RuntimeError(
                    f"workflow permission drift: unsupported job permission "
                    f"{workflow_path}#{job_id}:{scope}={level!r}"
                )
            if level == "write":
                scope_name = str(scope)
                if not _allows_write(scope_name, uses, runs):
                    raise RuntimeError(
                        "workflow permission drift: write permission lacks an approved "
                        f"same-job consumer: {workflow_path}#{job_id}:{scope_name}"
                    )
                job_writes.append(f"{job_id}:{scope_name}")

    return {
        "workflow": workflow_path,
        "default_contents": "read",
        "job_writes": sorted(job_writes),
    }


def audit_workflow_permissions(root: Path = ROOT) -> dict[str, object]:
    workflows_dir = root / ".github" / "workflows"
    paths = sorted((*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")))
    if not paths:
        raise RuntimeError("workflow permission audit: no workflow files found")
    evidence: list[dict[str, object]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        evidence.append(validate_workflow_permissions(relative, _workflow_document(path)))
    return {"scanned": len(paths), "workflows": evidence}


def validate_workflow_action_pins(root: Path = ROOT) -> dict[str, object]:
    workflows = root / ".github" / "workflows"
    paths = sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml")))
    if not paths:
        raise RuntimeError("workflow action pin audit: no workflow files found")
    findings: list[str] = []
    external_action_references = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in _ACTION_REF.finditer(text):
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            external_action_references += 1
            if "@" not in reference:
                findings.append(f"{path}: {reference}: external action has no immutable ref")
                continue
            _, ref = reference.rsplit("@", 1)
            if _FULL_SHA.fullmatch(ref) is None:
                findings.append(
                    f"{path}: {reference}: external action must be pinned to a full "
                    "40-character commit SHA"
                )
    if findings:
        raise RuntimeError("workflow action pin drift: " + "; ".join(findings))
    return {
        "scanned_files": len(paths),
        "external_action_references": external_action_references,
        "findings": [],
    }


def _codeowners_entries(text: str) -> list[tuple[str, tuple[str, ...]]]:
    entries: list[tuple[str, tuple[str, ...]]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            raise RuntimeError(f"CODEOWNERS malformed entry at line {line_number}")
        pattern = parts[0].lstrip("/")
        owners = tuple(parts[1:])
        if not all(owner.startswith("@") or "@" in owner for owner in owners):
            raise RuntimeError(f"CODEOWNERS malformed owner at line {line_number}")
        if pattern.endswith("/"):
            pattern += "**"
        entries.append((pattern, owners))
    if not entries:
        raise RuntimeError("CODEOWNERS has no ownership entries")
    return entries


def _coverage_probe(canonical_path: str) -> str:
    probe = canonical_path.lstrip("/")
    if probe.endswith("/**"):
        return probe[:-3].rstrip("/") + "/__coverage_probe__"
    if probe.endswith("/"):
        return probe + "__coverage_probe__"
    return probe


def validate_codeowners_coverage(
    critical_paths: list[str],
    codeowners_text: str,
) -> dict[str, object]:
    entries = _codeowners_entries(codeowners_text)
    coverage: dict[str, list[str]] = {}
    for critical_path in critical_paths:
        probe = _coverage_probe(critical_path)
        owners: tuple[str, ...] | None = None
        matched_pattern: str | None = None
        for pattern, candidate_owners in entries:
            if fnmatch.fnmatchcase(probe, pattern):
                owners = candidate_owners
                matched_pattern = pattern
        if owners is None or matched_pattern is None:
            raise RuntimeError(
                f"CODEOWNERS coverage drift: critical path {critical_path!r} is unowned"
            )
        coverage[critical_path] = [matched_pattern, *owners]
    return {"critical_paths": len(critical_paths), "coverage": coverage}


def validate_required_check_matrix(
    policy: Mapping[str, object],
    ci_workflow: Mapping[str, object],
) -> dict[str, object]:
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    raw_checks = h2.get("required_checks")
    if not isinstance(raw_checks, list):
        raise RuntimeError("h2.required_checks must be a list")
    configured_contexts = {
        str(_mapping(item, label="h2.required_check").get("context", ""))
        for item in raw_checks
    }

    jobs = _mapping(ci_workflow.get("jobs"), label="ci.jobs")
    quality_gate = _mapping(jobs.get("quality-gate"), label="ci.jobs.quality-gate")
    strategy = _mapping(quality_gate.get("strategy"), label="ci.quality-gate.strategy")
    matrix = _mapping(strategy.get("matrix"), label="ci.quality-gate.strategy.matrix")
    versions = matrix.get("python-version")
    if not isinstance(versions, list) or not versions:
        raise RuntimeError("CI matrix drift: python-version matrix must be a non-empty list")
    normalized_versions = [str(version) for version in versions]
    expected = {f"quality-gate ({version})" for version in normalized_versions}
    actual = {context for context in configured_contexts if context.startswith("quality-gate (")}
    if actual != expected:
        raise RuntimeError(
            "required-check matrix drift: "
            f"actual={sorted(actual)!r} expected={sorted(expected)!r}"
        )
    return {"python_versions": normalized_versions, "contexts": sorted(expected)}


def validate_periodic_drift_schedule(workflow_text: str) -> dict[str, str]:
    if not re.search(r"(?m)^\s{2}schedule:\s*$", workflow_text):
        raise RuntimeError("governance drift monitor: scheduled trigger is missing")
    match = re.search(r"(?m)^\s*-\s*cron:\s*[\"']?([^\"'\n]+)[\"']?\s*$", workflow_text)
    if match is None:
        raise RuntimeError("governance drift monitor: cron expression is missing")
    cron = match.group(1).strip()
    if len(cron.split()) != 5:
        raise RuntimeError("governance drift monitor: cron expression must have five fields")
    return {"cron": cron}


def build_static_evidence(candidate_sha: str, *, root: Path = ROOT) -> dict[str, object]:
    head_sha = _git("rev-parse", "HEAD") if root == ROOT else candidate_sha
    if head_sha != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head_sha} candidate={candidate_sha}")

    policy = _mapping(
        json.loads((root / "config" / "enterprise_v1.json").read_text(encoding="utf-8")),
        label="enterprise policy",
    )
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    raw_critical_paths = review.get("critical_paths")
    if not isinstance(raw_critical_paths, list) or not all(
        isinstance(item, str) and item for item in raw_critical_paths
    ):
        raise RuntimeError("h2.review_integrity.critical_paths must be a non-empty string list")
    critical_paths = cast(list[str], raw_critical_paths)

    permission_evidence = audit_workflow_permissions(root)
    action_pin_evidence = validate_workflow_action_pins(root)
    codeowners_evidence = validate_codeowners_coverage(
        critical_paths,
        (root / ".github" / "CODEOWNERS").read_text(encoding="utf-8"),
    )
    matrix_evidence = validate_required_check_matrix(
        policy,
        _workflow_document(root / ".github" / "workflows" / "ci.yml"),
    )
    schedule_evidence = validate_periodic_drift_schedule(
        (root / ".github" / "workflows" / "repository-governance-integrity.yml").read_text(
            encoding="utf-8"
        )
    )

    return {
        "schema": "lukart.repository-static-governance.v1",
        "candidate_sha": candidate_sha,
        "workflow_permissions": permission_evidence,
        "workflow_action_pins": action_pin_evidence,
        "codeowners": codeowners_evidence,
        "required_check_matrix": matrix_evidence,
        "periodic_drift_monitor": schedule_evidence,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed static repository governance policy gate"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/repository-static-governance.json",
    )
    args = parser.parse_args()
    try:
        evidence = build_static_evidence(args.candidate_sha)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"REPOSITORY_STATIC_GOVERNANCE=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPOSITORY_STATIC_GOVERNANCE=PASS")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
