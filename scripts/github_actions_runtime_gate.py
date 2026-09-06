from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

POLICY_RELATIVE_PATH = Path("config/github_actions_runtime_v1.json")
WORKFLOWS_RELATIVE_PATH = Path(".github/workflows")
POLICY_SCHEMA = "lukart.github-actions-runtime-policy.v1"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class RuntimeFinding:
    path: str
    reference: str
    reason: str


@dataclass(frozen=True, slots=True)
class RuntimeAuditReport:
    scanned_files: int
    external_action_references: int
    findings: tuple[RuntimeFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _load_policy(root: Path) -> Mapping[str, object]:
    path = root / POLICY_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load GitHub Actions runtime policy: {path}") from exc
    policy = _mapping(payload, label="runtime policy")
    if policy.get("schema") != POLICY_SCHEMA:
        observed_schema = policy.get("schema")
        raise RuntimeError(
            f"Unknown GitHub Actions runtime policy schema: {observed_schema!r}"
        )
    minimum = policy.get("minimum_node_runtime")
    if minimum != 24:
        raise RuntimeError(f"PH-01 requires minimum_node_runtime=24, got {minimum!r}")
    return policy


def _approved_actions(policy: Mapping[str, object]) -> Mapping[str, Mapping[str, object]]:
    raw = _mapping(policy.get("approved_actions"), label="approved_actions")
    approved: dict[str, Mapping[str, object]] = {}
    for identity, value in raw.items():
        if not isinstance(identity, str) or not identity:
            raise RuntimeError("Approved action identity must be a non-empty string")
        entry = _mapping(value, label=f"approved_actions.{identity}")
        sha = entry.get("sha")
        runtime = entry.get("runtime")
        if not isinstance(sha, str) or not FULL_SHA_RE.fullmatch(sha):
            raise RuntimeError(f"Approved action {identity} must bind a full 40-hex SHA")
        if runtime != "node24":
            raise RuntimeError(f"Approved action {identity} must be verified as node24")
        approved[identity] = entry
    if not approved:
        raise RuntimeError("approved_actions cannot be empty")
    return approved


def _workflow_paths(root: Path) -> tuple[Path, ...]:
    directory = root / WORKFLOWS_RELATIVE_PATH
    paths = sorted((*directory.glob("*.yml"), *directory.glob("*.yaml")))
    if not paths:
        raise RuntimeError(f"No GitHub Actions workflows found under {directory}")
    return tuple(paths)


def audit_workflow_action_runtime(root: Path) -> RuntimeAuditReport:
    root = root.resolve()
    policy = _load_policy(root)
    approved = _approved_actions(policy)
    findings: list[RuntimeFinding] = []
    references = 0
    paths = _workflow_paths(root)

    for workflow in paths:
        text = workflow.read_text(encoding="utf-8")
        relative = workflow.relative_to(root).as_posix()
        for match in USES_RE.finditer(text):
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            references += 1
            if "@" not in reference:
                findings.append(RuntimeFinding(relative, reference, "external action has no ref"))
                continue
            identity, ref = reference.rsplit("@", 1)
            if not FULL_SHA_RE.fullmatch(ref):
                findings.append(
                    RuntimeFinding(
                        relative,
                        reference,
                        "external action ref is not a full SHA",
                    )
                )
                continue
            entry = approved.get(identity)
            if entry is None:
                findings.append(
                    RuntimeFinding(
                        relative,
                        reference,
                        "external action identity is not runtime-verified in canonical policy",
                    )
                )
                continue
            expected_sha = entry["sha"]
            if ref != expected_sha:
                findings.append(
                    RuntimeFinding(
                        relative,
                        reference,
                        f"action SHA is not the verified Node24 binding {expected_sha}",
                    )
                )

    return RuntimeAuditReport(
        scanned_files=len(paths),
        external_action_references=references,
        findings=tuple(findings),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed GitHub Actions runtime continuity gate"
    )
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    try:
        report = audit_workflow_action_runtime(Path(args.root))
    except RuntimeError as exc:
        print(f"GITHUB_ACTIONS_RUNTIME_GATE=FAIL: {exc}")
        return 1

    print(f"WORKFLOWS_SCANNED={report.scanned_files}")
    print(f"EXTERNAL_ACTION_REFS={report.external_action_references}")
    for finding in report.findings:
        print(f"RUNTIME_POLICY_FAIL {finding.path}: {finding.reference} — {finding.reason}")
    if not report.passed:
        print("GITHUB_ACTIONS_RUNTIME_GATE=FAIL")
        return 1
    print("GITHUB_ACTIONS_RUNTIME_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
