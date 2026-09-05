"""Fail-closed effective-branch-rules validation for final release governance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_RELEASE_CHECKS = frozenset(
    {
        "quality-gate (3.11)",
        "quality-gate (3.12)",
        "quality-gate (3.13)",
        "program-gate",
        "gate",
        "orchestrate",
        "audit",
        "smoke-test",
    }
)


class ReleaseGovernanceError(RuntimeError):
    """Raised when effective main-branch governance is not release-safe."""


def _rules_by_type(rules: list[object], rule_type: str) -> list[dict[str, object]]:
    matches = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == rule_type
    ]
    if not matches:
        raise ReleaseGovernanceError(f"required branch rule is missing: {rule_type}")
    return matches


def validate_effective_main_rules(payload: object) -> None:
    """Validate active rules returned by GitHub's rules/branches/main endpoint."""

    if not isinstance(payload, list):
        raise ReleaseGovernanceError("effective branch rules response must be a list")

    _rules_by_type(payload, "pull_request")
    _rules_by_type(payload, "deletion")
    _rules_by_type(payload, "non_fast_forward")

    status_rules = _rules_by_type(payload, "required_status_checks")
    strict = False
    contexts: set[str] = set()
    for status_rule in status_rules:
        parameters = status_rule.get("parameters")
        if not isinstance(parameters, dict):
            raise ReleaseGovernanceError("required status checks parameters are missing")
        strict = strict or parameters.get("strict_required_status_checks_policy") is True
        raw_checks = parameters.get("required_status_checks")
        if not isinstance(raw_checks, list):
            raise ReleaseGovernanceError("required status check list is missing")
        contexts.update(
            item["context"]
            for item in raw_checks
            if isinstance(item, dict) and isinstance(item.get("context"), str)
        )

    if not strict:
        raise ReleaseGovernanceError(
            "required status checks must require the branch to be up to date"
        )

    missing = sorted(REQUIRED_RELEASE_CHECKS - contexts)
    if missing:
        raise ReleaseGovernanceError(
            "release-critical required checks are missing: " + ", ".join(missing)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-json", required=True)
    args = parser.parse_args()

    path = Path(args.rules_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGovernanceError("effective branch rules JSON is invalid") from exc

    validate_effective_main_rules(payload)
    print("RELEASE_GOVERNANCE_EFFECTIVE_RULES=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
