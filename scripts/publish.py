"""Validate and publish a private local case snapshot.

Case data is intentionally never committed or pushed to GitHub.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from factory.local_case_store import output_case_dir, validate_case_key
from knowledge.models.snapshot_validator import validate_snapshot


def load_snapshot(case_key: str, *, prefer: str = "freeze", data_root: Path | None = None) -> dict:
    base = output_case_dir(validate_case_key(case_key), data_root) / "snapshots"
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
    raise FileNotFoundError(f"No local snapshot under {base}. Run pipeline FREEZE first.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a private local case snapshot; never publish case data to GitHub"
    )
    parser.add_argument("--case", required=True, help="Private local case key")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
    parser.add_argument(
        "--prefer", choices=("freeze", "release", "latest"), default="freeze",
    )
    parser.add_argument("--commit", action="store_true", help="Rejected: case data is local-only")
    parser.add_argument("--push", action="store_true", help="Rejected: case data is local-only")
    parser.add_argument("--dry-run", action="store_true", help="Validate without write operations")
    args = parser.parse_args()

    if args.commit or args.push:
        print("PUBLISH BLOCKED: real case data is local-only; Git commit/push is disabled")
        return 1

    data_root = Path(args.data_root).expanduser() if args.data_root else None
    try:
        snap = load_snapshot(args.case, prefer=args.prefer, data_root=data_root)
    except (OSError, json.JSONDecodeError, FileNotFoundError, RuntimeError) as exc:
        print("PUBLISH BLOCKED:", exc)
        return 2

    phase = str(snap.get("phase", "")).upper()
    if phase and phase not in ("FREEZE", "RELEASE"):
        print(f"PUBLISH BLOCKED: phase must be FREEZE or RELEASE (got {phase!r})")
        return 1

    result = validate_snapshot(snap)
    print("Snapshot file:", snap.get("_snapshot_file"))
    print("Phase:", phase or "(missing)")
    print(result.report())
    print("Status field:", snap.get("status"))

    if not result.ready_to_publish:
        print("PUBLISH BLOCKED: snapshot not READY_TO_PUBLISH")
        return 1

    print("PUBLISH OK (local-only): snapshot is READY_TO_PUBLISH")
    if args.dry_run:
        print("No local write requested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
