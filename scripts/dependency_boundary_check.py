"""Fail CI when runtime packages import development factory modules."""

from __future__ import annotations

import ast
from pathlib import Path

RUNTIME_ROOTS = ("core", "knowledge", "learning", "reasoning", "renderer")


def runtime_factory_imports(root: Path) -> list[str]:
    violations: list[str] = []
    for package in RUNTIME_ROOTS:
        package_root = root / package
        if not package_root.is_dir():
            continue
        for path in sorted(package_root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported = [node.module]
                else:
                    continue
                for module in imported:
                    if module == "factory" or module.startswith("factory."):
                        violations.append(
                            f"{path.relative_to(root)}:{node.lineno}:{module}"
                        )
    return violations


def main() -> int:
    root = Path.cwd().resolve()
    violations = runtime_factory_imports(root)
    if violations:
        print("Runtime/factory dependency violations:")
        print("\n".join(violations))
        return 1
    print("Dependency boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
