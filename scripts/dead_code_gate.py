"""Deterministic inventory of Python modules with no in-repository imports."""

from __future__ import annotations

import ast
from pathlib import Path


def module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def referenced_modules(root: Path) -> set[str]:
    refs: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                refs.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                refs.add(node.module)
    return refs


def unreferenced_modules(root: Path) -> list[str]:
    refs = referenced_modules(root)
    modules = {
        module_name(root, path)
        for path in root.rglob("*.py")
        if path.name != "__init__.py"
        and not any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts)
    }
    return sorted(module for module in modules if module not in refs)


def main() -> int:
    root = Path.cwd().resolve()
    inventory = unreferenced_modules(root)
    print("DEAD_CODE_INVENTORY")
    for module in inventory:
        print(module)
    print(f"UNREFERENCED_MODULE_COUNT={len(inventory)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
