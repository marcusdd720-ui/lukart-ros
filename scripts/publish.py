"""
Publish gate: only acts when a FREEZE (or RELEASE) snapshot is READY_TO_PUBLISH.

Does not run pipeline, agents, or renderers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.snapshot_validator import validate_snapshot


def load_snapshot(case_key: str, *, prefer: str = "freeze") -> dict:
    base = ROOT / "output" / "cases" / case_key / "snapshots"
    candidates = [
        base / f"latest_{prefer}.json",
        base / "latest_freeze.json",
        base / "latest.json",
        base / "latest_release.json",
    ]
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_snapshot_file"] = str(path)
            return data
    raise FileNotFoundError(
        f"No freeze/latest snapshot under {base}. Run pipeline FREEZE first."
    )


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish case outputs if FREEZE snapshot is READY_TO_PUBLISH"
    )
    parser.add_argument(
        "--case",
        default="DS_3960_2025",
        help="Case folder key under cases/",
    )
    parser.add_argument(
        "--prefer",
        choices=("freeze", "release", "latest"),
        default="freeze",
        help="Which latest pointer to load (default: freeze)",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="git add case output paths and commit before push",
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

    prefer = "latest" if args.prefer == "latest" else args.prefer

    try:
        snap = load_snapshot(args.case, prefer=prefer)
    except (OSError, json.JSONDecodeError, FileNotFoundError) as exc:
        print("PUBLISH BLOCKED:", exc)
        return 2

    phase = str(snap.get("phase", "")).upper()
    print("Snapshot file:", snap.get("_snapshot_file"))
    print("Phase:", phase or "(missing)")

    if phase and phase not in ("FREEZE", "RELEASE"):
        print(f"PUBLISH BLOCKED: phase must be FREEZE or RELEASE (got {phase!r})")
        return 1

    result = validate_snapshot(snap)
    print(result.report())
    print("Status field:", snap.get("status"))
    print("Case:", snap.get("case_key"))
    print("Dossier:", snap.get("dossier_path"))

    if not result.ready_to_publish:
        print("PUBLISH BLOCKED: snapshot not READY_TO_PUBLISH")
        return 1

    if args.dry_run or (not args.commit and not args.push):
        print("PUBLISH OK (dry): FREEZE/RELEASE allows publish")
        if not args.commit and not args.push and not args.dry_run:
            print("Hint: pass --commit and/or --push to perform git actions")
        return 0

    if args.commit:
        paths = [
            f"output/cases/{args.case}",
            f"cases/{args.case}",
            "knowledge/models/case_workspace.py",
            "knowledge/models/case_snapshot.py",
            "knowledge/models/snapshot_validator.py",
            "scripts/publish.py",
        ]
        existing = [p for p in paths if (ROOT / p).exists()]
        add = run_git(["add", *existing])
        if add.returncode != 0:
            print(add.stderr)
            return add.returncode
        msg = (
            f"Publish {args.case} {phase or 'FREEZE'} "
            f"{str(snap.get('snapshot_id', ''))[:8]} READY_TO_PUBLISH"
        )
        commit = run_git(["commit", "-m", msg])
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