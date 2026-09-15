"""Fail-closed execution contracts for CASE-TESTY test profiles."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


class ProfileName(StrEnum):
    FAST = "FAST"
    PR = "PR"
    FULL = "FULL"
    FORENSIC = "FORENSIC"
    POST_MERGE = "POST-MERGE"


class StepStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ProfileStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class TestStep:
    name: str
    command: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class TestProfile:
    name: ProfileName
    steps: tuple[TestStep, ...]
    required_step_names: tuple[str, ...]


@dataclass(frozen=True)
class StepResult:
    name: str
    command: tuple[str, ...]
    required: bool
    status: StepStatus
    exit_code: int | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": list(self.command),
            "required": self.required,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProfileResult:
    profile: ProfileName
    git_sha: str
    status: ProfileStatus
    steps: tuple[StepResult, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile.value,
            "git_sha": self.git_sha,
            "status": self.status.value,
            "reason": self.reason,
            "steps": [step.to_dict() for step in self.steps],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


StepExecutor = Callable[[TestStep], StepResult]


PROFILE_DEFINITIONS: dict[ProfileName, TestProfile] = {
    ProfileName.FAST: TestProfile(
        name=ProfileName.FAST,
        steps=(
            TestStep(
                name="runner-self-tests",
                command=("python", "-m", "pytest", "tests/profiles/test_test_profiles.py", "-q"),
            ),
        ),
        required_step_names=("runner-self-tests",),
    ),
    ProfileName.PR: TestProfile(
        name=ProfileName.PR,
        steps=(
            TestStep(
                name="runner-self-tests",
                command=("python", "-m", "pytest", "tests/profiles/test_test_profiles.py", "-q"),
            ),
            TestStep(
                name="stage-0",
                command=("python", "-m", "factory.stage_gate", "--stage", "0"),
            ),
        ),
        required_step_names=("runner-self-tests", "stage-0"),
    ),
    ProfileName.FULL: TestProfile(
        name=ProfileName.FULL,
        steps=(
            TestStep(
                name="runner-self-tests",
                command=("python", "-m", "pytest", "tests/profiles/test_test_profiles.py", "-q"),
            ),
            TestStep(
                name="stage-0",
                command=("python", "-m", "factory.stage_gate", "--stage", "0"),
            ),
            TestStep(
                name="stage-16",
                command=("python", "-m", "factory.stage_gate", "--stage", "16"),
            ),
            TestStep(
                name="certification-tests",
                command=("python", "-m", "pytest", "certification_tests", "-q"),
            ),
        ),
        required_step_names=(
            "runner-self-tests",
            "stage-0",
            "stage-16",
            "certification-tests",
        ),
    ),
    ProfileName.FORENSIC: TestProfile(
        name=ProfileName.FORENSIC,
        steps=(
            TestStep(
                name="runner-self-tests",
                command=("python", "-m", "pytest", "tests/profiles/test_test_profiles.py", "-q"),
            ),
            TestStep(
                name="stage-0",
                command=("python", "-m", "factory.stage_gate", "--stage", "0"),
            ),
            TestStep(
                name="stage-16",
                command=("python", "-m", "factory.stage_gate", "--stage", "16"),
            ),
            TestStep(
                name="certification-tests",
                command=("python", "-m", "pytest", "certification_tests", "-q"),
            ),
        ),
        required_step_names=(
            "runner-self-tests",
            "stage-0",
            "stage-16",
            "certification-tests",
        ),
    ),
    ProfileName.POST_MERGE: TestProfile(
        name=ProfileName.POST_MERGE,
        steps=(
            TestStep(
                name="runner-self-tests",
                command=("python", "-m", "pytest", "tests/profiles/test_test_profiles.py", "-q"),
            ),
            TestStep(
                name="stage-0",
                command=("python", "-m", "factory.stage_gate", "--stage", "0"),
            ),
            TestStep(
                name="stage-16",
                command=("python", "-m", "factory.stage_gate", "--stage", "16"),
            ),
            TestStep(
                name="certification-tests",
                command=("python", "-m", "pytest", "certification_tests", "-q"),
            ),
        ),
        required_step_names=(
            "runner-self-tests",
            "stage-0",
            "stage-16",
            "certification-tests",
        ),
    ),
}


def execute_step(step: TestStep, *, cwd: Path | None = None) -> StepResult:
    if not step.command:
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.FAIL,
            exit_code=None,
            reason="missing command: command list is empty",
        )

    try:
        completed = subprocess.run(
            step.command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        missing = exc.filename or step.command[0]
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.FAIL,
            exit_code=None,
            reason=f"missing command: {missing}",
        )
    except Exception as exc:
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.FAIL,
            exit_code=None,
            reason=f"executor exception: {type(exc).__name__}: {exc}",
        )

    if completed.returncode == 0:
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.PASS,
            exit_code=0,
            reason="exit code 0",
        )

    return StepResult(
        name=step.name,
        command=step.command,
        required=step.required,
        status=StepStatus.FAIL,
        exit_code=completed.returncode,
        reason=f"exit code {completed.returncode}",
    )


def _profile_contract_failures(profile: TestProfile) -> tuple[StepResult, ...]:
    failures: list[StepResult] = []
    if not profile.required_step_names:
        failures.append(
            StepResult(
                name="__profile_contract__",
                command=(),
                required=True,
                status=StepStatus.FAIL,
                exit_code=None,
                reason="profile has no required steps",
            )
        )
        return tuple(failures)

    names = [step.name for step in profile.steps]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        failures.append(
            StepResult(
                name="__profile_contract__",
                command=(),
                required=True,
                status=StepStatus.FAIL,
                exit_code=None,
                reason=f"duplicate step names: {', '.join(duplicate_names)}",
            )
        )

    by_name = {step.name: step for step in profile.steps}
    for required_name in profile.required_step_names:
        step = by_name.get(required_name)
        if step is None:
            failures.append(
                StepResult(
                    name=required_name,
                    command=(),
                    required=True,
                    status=StepStatus.FAIL,
                    exit_code=None,
                    reason="required step missing from profile definition",
                )
            )
        elif not step.required:
            failures.append(
                StepResult(
                    name=required_name,
                    command=step.command,
                    required=True,
                    status=StepStatus.FAIL,
                    exit_code=None,
                    reason="required step is marked optional",
                )
            )

    required_manifest = set(profile.required_step_names)
    for step in profile.steps:
        if step.required and step.name not in required_manifest:
            failures.append(
                StepResult(
                    name=step.name,
                    command=step.command,
                    required=True,
                    status=StepStatus.FAIL,
                    exit_code=None,
                    reason="required step omitted from required-step manifest",
                )
            )

    return tuple(failures)


def _normalize_result(step: TestStep, result: StepResult) -> StepResult:
    status = result.status
    reason = result.reason

    if status is StepStatus.PASS and result.exit_code != 0:
        status = StepStatus.FAIL
        reason = f"invalid PASS: exit code must be 0, got {result.exit_code}"
    elif status is StepStatus.UNKNOWN and step.required:
        status = StepStatus.FAIL
        reason = f"required step returned UNKNOWN: {result.reason}"

    return StepResult(
        name=step.name,
        command=step.command,
        required=step.required,
        status=status,
        exit_code=result.exit_code,
        reason=reason,
    )


def run_profile(
    profile: TestProfile,
    git_sha: str,
    *,
    executor: StepExecutor | None = None,
    cwd: Path | None = None,
) -> ProfileResult:
    if _FULL_SHA.fullmatch(git_sha) is None:
        return ProfileResult(
            profile=profile.name,
            git_sha=git_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason="git SHA must be an exact 40-character hexadecimal commit SHA",
        )

    contract_failures = _profile_contract_failures(profile)
    if contract_failures:
        return ProfileResult(
            profile=profile.name,
            git_sha=git_sha.lower(),
            status=ProfileStatus.FAIL,
            steps=contract_failures,
            reason="profile contract is invalid",
        )

    def execute_with_cwd(step: TestStep) -> StepResult:
        return execute_step(step, cwd=cwd)

    selected_executor: StepExecutor = executor if executor is not None else execute_with_cwd

    results: list[StepResult] = []
    for step in profile.steps:
        try:
            raw_result = selected_executor(step)
        except Exception as exc:
            raw_result = StepResult(
                name=step.name,
                command=step.command,
                required=step.required,
                status=StepStatus.FAIL,
                exit_code=None,
                reason=f"executor exception: {type(exc).__name__}: {exc}",
            )
        results.append(_normalize_result(step, raw_result))

    required_failed = any(
        result.required and result.status is not StepStatus.PASS for result in results
    )
    status = ProfileStatus.FAIL if required_failed else ProfileStatus.PASS
    reason = "one or more required steps failed" if required_failed else "all required steps passed"
    return ProfileResult(
        profile=profile.name,
        git_sha=git_sha.lower(),
        status=status,
        steps=tuple(results),
        reason=reason,
    )


def _resolve_git_sha(explicit_sha: str | None) -> tuple[str, str | None]:
    if explicit_sha is not None:
        return explicit_sha, None

    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha, None

    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return "", f"cannot resolve git SHA: {type(exc).__name__}: {exc}"

    if completed.returncode != 0:
        return "", f"cannot resolve git SHA: git rev-parse exited {completed.returncode}"
    return completed.stdout.strip(), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=[profile.value for profile in ProfileName])
    parser.add_argument("--sha", dest="git_sha")
    args = parser.parse_args()

    profile_name = ProfileName(args.profile)
    git_sha, resolution_error = _resolve_git_sha(args.git_sha)
    if resolution_error is not None:
        result = ProfileResult(
            profile=profile_name,
            git_sha=git_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason=resolution_error,
        )
    else:
        result = run_profile(PROFILE_DEFINITIONS[profile_name], git_sha)

    print(result.to_json())
    return 0 if result.status is ProfileStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
