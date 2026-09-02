"""Create a new MVROS case in the private local data store."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from factory.local_case_store import case_dir, ensure_data_root

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "cases" / "_TEMPLATE"


def slugify(name: str) -> str:
    text = name.strip().replace(" ", "_")
    text = re.sub(r"[^\w\-.]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NOWA_SPRAWA"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a case outside the Git repository")
    parser.add_argument("name", help="Private local working name of the case")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing local case")
    args = parser.parse_args()

    if not TEMPLATE.is_dir():
        print(f"ERROR: template not found: {TEMPLATE}")
        return 1

    try:
        data_root = ensure_data_root(Path(args.data_root).expanduser() if args.data_root else None)
        case_name = slugify(args.name)
        target = case_dir(case_name, data_root, repo_root=ROOT)
    except (OSError, ValueError, RuntimeError) as exc:
        print("PRIVACY BLOCKED:", exc)
        return 1

    if target.exists() and not args.force:
        print(f"ERROR: already exists: {target}")
        return 1
    if target.exists():
        shutil.rmtree(target)

    shutil.copytree(TEMPLATE, target)
    readme = target / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("[NAZWA_ROBOCZA]", case_name), encoding="utf-8")

    print("Created private local case:", target)
    for sub in ("outbound", "inbound", "notes", "evidence"):
        print(" ", sub, "OK" if (target / sub).is_dir() else "MISSING")
    print("GitHub upload: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())