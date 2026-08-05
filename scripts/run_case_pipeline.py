"""
Case pipeline – thin CLI over CaseWorkspace.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.case_workspace import open_ds_3960


def main() -> int:
    parser = argparse.ArgumentParser(description="Run case workspace pipeline")
    parser.add_argument(
        "--case",
        default="DS_3960_2025",
        help="Case key (currently only DS_3960_2025 is wired)",
    )
    args = parser.parse_args()

    if args.case != "DS_3960_2025":
        print(f"Unsupported case key: {args.case}")
        print("Wired adapters: DS_3960_2025")
        return 2

    ws = open_ds_3960()
    return ws.run(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
    )


if __name__ == "__main__":
    raise SystemExit(main())