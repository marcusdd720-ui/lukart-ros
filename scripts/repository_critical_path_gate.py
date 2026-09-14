from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"
_GLOB_META = frozenset("*?[")


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


def _safe_pattern(raw: str) -> str:
    if not raw or "\\" in raw:
        raise RuntimeError(f"critical path is invalid: {raw!r}")
    path = PurePosixPath(raw.lstrip("/"))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"critical path escapes repository: {raw!r}")
    return path.as_posix()


def validate_critical_paths(root: Path, critical_paths: list[str]) -> dict[str, object]:
    if not critical_paths:
        raise RuntimeError("critical path inventory must not be empty")
    if len(set(critical_paths)) != len(critical_paths):
        raise RuntimeError("critical path inventory contains duplicates")

    exact_files: list[str] = []
    subtrees: list[str] = []
    patterns: list[str] = []
    for raw in critical_paths:
        pattern = _safe_pattern(raw)
        if pattern.endswith("/**"):
            base = root / pattern[:-3].rstrip("/")
            if not base.is_dir():
                raise RuntimeError(
                    f"critical path subtree is missing: {raw!r}"
                )
            if not any(item.is_file() for item in base.rglob("*")):
                raise RuntimeError(
                    f"critical path subtree has no tracked files: {raw!r}"
                )
            subtrees.append(pattern)
            continue

        if any(char in pattern for char in _GLOB_META):
            matches = [item for item in root.glob(pattern) if item.exists()]
            if not matches:
                raise RuntimeError(
                    f"critical path pattern has no repository matches: {raw!r}"
                )
            patterns.append(pattern)
            continue

        candidate = root / pattern
        if not candidate.is_file():
            raise RuntimeError(
                f"critical exact artifact is missing: {raw!r}"
            )
        exact_files.append(pattern)

    return {
        "critical_paths": len(critical_paths),
        "exact_files": sorted(exact_files),
        "subtrees": sorted(subtrees),
        "patterns": sorted(patterns),
    }


def build_evidence(candidate_sha: str, *, root: Path = ROOT) -> dict[str, object]:
    head = _git("rev-parse", "HEAD") if root == ROOT else candidate_sha
    if head != candidate_sha:
        raise RuntimeError(f"exact-SHA mismatch: HEAD={head} candidate={candidate_sha}")
    try:
        policy = _mapping(
            json.loads((root / "config" / "enterprise_v1.json").read_text(encoding="utf-8")),
            label="enterprise policy",
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("enterprise policy must be valid UTF-8 JSON") from exc
    h2 = _mapping(policy.get("h2_repository_policy"), label="h2_repository_policy")
    review = _mapping(h2.get("review_integrity"), label="h2.review_integrity")
    raw_paths = review.get("critical_paths")
    if not isinstance(raw_paths, list) or any(
        not isinstance(item, str) or not item for item in raw_paths
    ):
        raise RuntimeError("h2.review_integrity.critical_paths must be a string list")
    integrity = validate_critical_paths(root, cast(list[str], raw_paths))
    return {
        "schema": "lukart.repository-critical-path-integrity.v1",
        "candidate_sha": candidate_sha,
        "inventory": integrity,
        "state": "CONTROL_PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed canonical critical-path integrity gate"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/repository-critical-path-integrity.json",
    )
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.candidate_sha)
    except RuntimeError as exc:
        print(f"REPOSITORY_CRITICAL_PATH_INTEGRITY=FAIL: {exc}")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("REPOSITORY_CRITICAL_PATH_INTEGRITY=PASS")
    print(f"CANDIDATE_SHA={evidence['candidate_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
