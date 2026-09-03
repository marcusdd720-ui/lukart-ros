"""Produce a measured inventory of Python model modules imported by runtime code."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path


def model_usage(root: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in sorted((root / "core").rglob("*.py")) + sorted((root / "knowledge").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.startswith("core.models.") or name.startswith("knowledge.models."):
                    counts[name] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    root = Path.cwd().resolve()
    report = model_usage(root)
    print("MODEL_USAGE_AUDIT")
    for name, count in report.items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
