"""
Case pipeline – thin CLI over CaseSpec registry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.case_registry import get_spec, registered_keys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run case workspace pipeline")
    parser.add_argument(
        "--case",
        default="DS_3960_2025",
        help="Case key registered in case_registry",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered case keys and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("Registered cases:")
        for key in registered_keys():
            print(f"  - {key}")
        return 0

    try:
        spec = get_spec(args.case)
    except KeyError as exc:
        print(exc)
        return 2

    ws = spec.open()
    return ws.run(**spec.run_kwargs())


if __name__ == "__main__":
    raise SystemExit(main())