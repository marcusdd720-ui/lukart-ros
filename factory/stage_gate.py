"""Automated stage gate runner for the LukArt ROS Factory."""

import argparse
import platform
import subprocess

from factory.stage_registry import get_stage, next_stage

COMMANDS: dict[str, tuple[str, ...]] = {
    "quality": (
        "python -m ruff check .",
        "python -m mypy .",
        "python -m pytest -v",
    ),
    "kqm": ("python -m validation.kqm_experiment",),
    "extraction": ("python -m pytest tests/test_fact_projection.py -q",),
    "projection": ("python -m pytest tests/test_fact_projection.py -q",),
    "e2e": ("python -m pytest tests/test_pipeline_fact_e2e.py -q",),
    "audit": (
        "python -m ruff check .",
        "python -m mypy .",
        "python -m pytest -v",
        "python -m validation.kqm_experiment",
        "python scripts/repository_audit.py",
        "python scripts/pii_scan.py",
    ),
    "contract": (
        "python -m pytest tests/test_fact_contract.py -q",
        "python -m pytest -v",
        "python scripts/repository_audit.py",
        "python scripts/pii_scan.py",
    ),
    "dedup": (
        "python -m pytest tests/test_fact_identity.py -q",
        "python -m pytest tests/test_fact_projection.py tests/test_pipeline_fact_e2e.py -q",
        "python -m pytest -v",
        "python -m ruff check .",
        "python -m mypy .",
        "python scripts/repository_audit.py",
        "python scripts/pii_scan.py",
    ),
    "relations": (
        "python -m pytest tests/test_relation_layer.py -q",
        "python -m pytest tests/test_fact_projection.py tests/test_pipeline_fact_e2e.py -q",
        "python -m pytest -v",
        "python -m ruff check .",
        "python -m mypy .",
        "python scripts/repository_audit.py",
        "python scripts/pii_scan.py",
    ),
}


def run(command: str) -> int:
    print(f"[stage-gate] {command}")
    completed = subprocess.run(command, shell=True, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, required=True)
    args = parser.parse_args()

    stage = get_stage(args.stage)
    commands = COMMANDS.get(stage.gate)
    if commands is None:
        print(f"Stage {stage.number}: {stage.name}")
        print("Gate: NOT IMPLEMENTED")
        print("This stage is registered but its executable gate is not ready yet.")
        return 2

    print(f"Stage {stage.number}: {stage.name}")
    print(f"Gate: {stage.gate}")
    for command in commands:
        is_python_311_only = any(
            marker in command
            for marker in ("scripts/repository_audit.py", "scripts/pii_scan.py")
        )
        if is_python_311_only and platform.python_version_tuple()[:2] != ("3", "11"):
            continue
        if run(command) != 0:
            print(f"STAGE {stage.number}: FAIL")
            return 1

    following = next_stage(stage.number)
    print(f"STAGE {stage.number}: PASS")
    if following is not None:
        print(f"NEXT_STAGE={following.number}")
        print(f"NEXT_STAGE_NAME={following.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
