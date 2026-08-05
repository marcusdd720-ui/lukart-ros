"""Create a new case folder from cases/_TEMPLATE."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "cases" / "_TEMPLATE"
CASES = ROOT / "cases"


def slugify(name: str) -> str:
    text = name.strip().replace(" ", "_")
    text = re.sub(r"[^\w\-.]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NOWA_SPRAWA"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create cases/<NAME>/ from cases/_TEMPLATE",
    )
    parser.add_argument(
        "name",
        help="Working name of the case (e.g. Pani_Sylwia or DS_1234_2026)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing case folder contents (dangerous)",
    )
    args = parser.parse_args()

    if not TEMPLATE.is_dir():
        print(f"ERROR: template not found: {TEMPLATE}")
        return 1

    case_name = slugify(args.name)
    target = CASES / case_name

    if target.exists() and not args.force:
        print(f"ERROR: already exists: {target}")
        print("Use another name or --force")
        return 1

    if target.exists() and args.force:
        shutil.rmtree(target)

    shutil.copytree(TEMPLATE, target)

    readme = target / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = text.replace("[NAZWA_ROBOCZA]", case_name)
        readme.write_text(text, encoding="utf-8")

    print("Created:", target)
    for sub in ("outbound", "inbound", "notes", "evidence"):
        print(" ", sub, "OK" if (target / sub).is_dir() else "MISSING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())