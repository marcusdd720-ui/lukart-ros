from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

REQUIRED_TRUST_BOUNDARIES = {
    "core.enterprise.api_guard",
    "core.enterprise.authorization",
    "core.enterprise.contracts",
    "core.enterprise.durability",
    "core.p3.contracts",
    "core.p3.versioning",
    "validation.release_governance",
}


def _strict_override() -> dict[str, object]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    overrides = data["tool"]["mypy"]["overrides"]
    for override in overrides:
        modules = set(override.get("module", []))
        if REQUIRED_TRUST_BOUNDARIES <= modules:
            return override
    raise AssertionError("PH-04 strict trust-boundary override is missing")


def _module_path(module: str) -> Path:
    return ROOT.joinpath(*module.split(".")).with_suffix(".py")


def _function_is_fully_annotated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.returns is None:
        return False
    positional = [*node.args.posonlyargs, *node.args.args]
    for index, argument in enumerate(positional):
        if index == 0 and argument.arg in {"self", "cls"}:
            continue
        if argument.annotation is None:
            return False
    if any(argument.annotation is None for argument in node.args.kwonlyargs):
        return False
    if node.args.vararg is not None and node.args.vararg.annotation is None:
        return False
    if node.args.kwarg is not None and node.args.kwarg.annotation is None:
        return False
    return True


def test_ph04_mypy_checks_untyped_function_bodies_globally() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    mypy = data["tool"]["mypy"]
    assert mypy["check_untyped_defs"] is True


def test_ph04_trust_boundaries_are_targeted_strict_and_no_blanket_ignore() -> None:
    override = _strict_override()
    assert override["disallow_untyped_defs"] is True
    assert override["disallow_incomplete_defs"] is True
    assert override["no_implicit_optional"] is True
    assert override["strict_equality"] is True
    assert override["warn_return_any"] is True
    assert override.get("ignore_errors") is not True


def test_ph04_trust_boundary_surface_is_fully_annotated() -> None:
    checked_functions = 0
    failures: list[str] = []
    for module in sorted(REQUIRED_TRUST_BOUNDARIES):
        path = _module_path(module)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            checked_functions += 1
            if not _function_is_fully_annotated(node):
                failures.append(f"{module}:{node.lineno}:{node.name}")
    assert checked_functions > 0
    assert failures == []


def test_ph04_negative_untyped_definition_is_detected() -> None:
    tree = ast.parse("def unsafe(value):\n    return value\n")
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    assert _function_is_fully_annotated(node) is False
