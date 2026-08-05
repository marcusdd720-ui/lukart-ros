"""
Publish gate: only pushes when CaseSnapshot status is READY_TO_PUBLISH.

Does not run pipeline, agents, or renderers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lukart.snapshot.v1"


def load_latest(case_key: str) -> dict:
    path = ROOT / "output" / "cases" / case_key / "snapshots" / "latest.json"
    if not path.is_file():
        raise FileNotFoundError(f"No snapshot: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"Bad schema: {data.get('schema')!r}")
    return data


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish case outputs if snapshot READY_TO_PUBLISH")
    parser.add_argument("--case", default="DS_3960_2025", help="Case folder key under cases/")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="git add case output/snapshot paths and commit before push",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="git push after checks (and optional commit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate snapshot; no git write operations",
    )
    args = parser.parse_args()

    try:
        snap = load_latest(args.case)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("PUBLISH BLOCKED:", exc)
        return 2

    status = snap.get("status")
    print("Snapshot status:", status)
    print("Case:", snap.get("case_key"))
    print("Git commit (at run):", snap.get("git_commit"))
    print("Dossier:", snap.get("dossier_path"))

    if status != "READY_TO_PUBLISH":
        print("PUBLISH BLOCKED: status is not READY_TO_PUBLISH")
        return 1

    if args.dry_run or (not args.commit and not args.push):
        print("PUBLISH OK (dry): snapshot allows publish")
        if not args.commit and not args.push and not args.dry_run:
            print("Hint: pass --commit and/or --push to perform git actions")
        return 0

    if args.commit:
        paths = [
            f"output/cases/{args.case}",
            f"cases/{args.case}",
            "knowledge/models/case_workspace.py",
            "knowledge/models/case_snapshot.py",
        ]
        existing = [p for p in paths if (ROOT / p).exists()]
        add = run_git(["add", *existing])
        if add.returncode != 0:
            print(add.stderr)
            return add.returncode
        msg = f"Publish {args.case} snapshot {snap.get('snapshot_id', '')[:8]} READY_TO_PUBLISH"
        commit = run_git(["commit", "-m", msg])
        # exit 1 often means "nothing to commit" – treat as OK
        if commit.returncode not in (0, 1):
            print(commit.stdout)
            print(commit.stderr)
            return commit.returncode
        print(commit.stdout.strip() or "commit: nothing new or done")

    if args.push:
        push = run_git(["push"])
        print(push.stdout)
        if push.returncode != 0:
            print(push.stderr)
            print("PUBLISH FAIL: git push")
            return push.returncode
        print("PUBLISH DONE: pushed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())