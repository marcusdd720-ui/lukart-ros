"""Fail-closed execution contracts for CASE-TESTY test profiles."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from factory.quality.report_schema import REPORT_SCHEMA

_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_STEP_TIMEOUT_SECONDS = 900


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
    timeout_seconds: int = DEFAULT_STEP_TIMEOUT_SECONDS


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
    required_steps: tuple[str, ...]
    started_at: str
    ended_at: str
    repository: str
    ref: str
    checkout_sha: str
    schema_version: str = REPORT_SCHEMA

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "ref": self.ref,
            "git_sha": self.git_sha,
            "checkout_sha": self.checkout_sha,
            "profile": self.profile.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "required_steps": list(self.required_steps),
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "reason": self.reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


StepExecutor = Callable[[TestStep], StepResult]

_P0_REGRESSION_COMMAND = (
    "python",
    "-m",
    "pytest",
    "tests/case/test_case_ledger_isolation.py",
    "tests/security/test_tenant_case_isolation.py",
    "tests/case/test_cirp_preflight_lifecycle.py",
    "tests/case/test_external_action_lifecycle.py",
    "tests/case/test_cirp_evidence_semantics.py",
    "tests/test_stage_gate_fail_closed.py",
    "tests/case/test_case_ledger_integrity.py",
    "-q",
)
_RUNNER_TEST_COMMAND = (
    "python",
    "-m",
    "pytest",
    "tests/profiles/test_test_profiles.py",
    "tests/profiles/test_test_report.py",
    "-q",
)


def _valid_timeout_seconds(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _step(
    name: str,
    *command: str,
    timeout_seconds: int = DEFAULT_STEP_TIMEOUT_SECONDS,
) -> TestStep:
    return TestStep(
        name=name,
        command=tuple(command),
        timeout_seconds=timeout_seconds,
    )


def _profile(name: ProfileName, steps: tuple[TestStep, ...]) -> TestProfile:
    return TestProfile(
        name=name,
        steps=steps,
        required_step_names=tuple(step.name for step in steps if step.required),
    )


PROFILE_DEFINITIONS: dict[ProfileName, TestProfile] = {
    ProfileName.FAST: _profile(
        ProfileName.FAST,
        (
            TestStep("runner-self-tests", _RUNNER_TEST_COMMAND),
            TestStep("p0-regressions", _P0_REGRESSION_COMMAND),
        ),
    ),
    ProfileName.PR: _profile(
        ProfileName.PR,
        (
            TestStep("p0-regressions", _P0_REGRESSION_COMMAND),
            _step("ruff", "python", "-m", "ruff", "check", "."),
            _step("mypy", "python", "-m", "mypy", "."),
            _step("stage-0", "python", "-m", "factory.stage_gate", "--stage", "0"),
        ),
    ),
    ProfileName.FULL: _profile(
        ProfileName.FULL,
        (
            _step("pytest", "python", "-m", "pytest"),
            _step("ruff", "python", "-m", "ruff", "check", "."),
            _step("mypy", "python", "-m", "mypy", "."),
            _step("stage-0", "python", "-m", "factory.stage_gate", "--stage", "0"),
            _step("stage-16", "python", "-m", "factory.stage_gate", "--stage", "16"),
            _step("certification-tests", "python", "-m", "pytest", "certification_tests", "-q"),
        ),
    ),
    ProfileName.FORENSIC: _profile(
        ProfileName.FORENSIC,
        (
            _step("full-regression", "python", "-m", "pytest"),
            _step(
                "adversarial-gold",
                "python",
                "-m",
                "pytest",
                "tests/test_adversarial_gold.py",
                "-q",
            ),
            _step("security", "python", "-m", "pytest", "tests/security", "-q"),
            TestStep("p0-regressions", _P0_REGRESSION_COMMAND),
            _step("certification-tests", "python", "-m", "pytest", "certification_tests", "-q"),
            _step("stage-16", "python", "-m", "factory.stage_gate", "--stage", "16"),
        ),
    ),
    ProfileName.POST_MERGE: _profile(
        ProfileName.POST_MERGE,
        (
            _step("pytest", "python", "-m", "pytest"),
            _step("ruff", "python", "-m", "ruff", "check", "."),
            _step("mypy", "python", "-m", "mypy", "."),
            _step("stage-0", "python", "-m", "factory.stage_gate", "--stage", "0"),
            _step("stage-16", "python", "-m", "factory.stage_gate", "--stage", "16"),
            _step("certification-tests", "python", "-m", "pytest", "certification_tests", "-q"),
        ),
    ),
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _metadata() -> tuple[str, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "local")
    ref = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "local"
    return repository, ref


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

    if not _valid_timeout_seconds(
        step.timeout_seconds
    ):
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.FAIL,
            exit_code=None,
            reason=(
                "invalid timeout_seconds: "
                "must be a positive integer"
            ),
        )

    command = (
        (sys.executable, *step.command[1:])
        if step.command[0] == "python"
        else step.command
    )

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=step.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return StepResult(
            name=step.name,
            command=step.command,
            required=step.required,
            status=StepStatus.FAIL,
            exit_code=None,
            reason=(
                f"timeout after "
                f"{step.timeout_seconds}s"
            ),
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
        return (
            StepResult(
                name="__profile_contract__",
                command=(),
                required=True,
                status=StepStatus.FAIL,
                exit_code=None,
                reason="profile has no required steps",
            ),
        )
    for profile_step in profile.steps:
        if not _valid_timeout_seconds(
            profile_step.timeout_seconds
        ):
            failures.append(
                StepResult(
                    name=profile_step.name,
                    command=profile_step.command,
                    required=profile_step.required,
                    status=StepStatus.FAIL,
                    exit_code=None,
                    reason=(
                        "invalid timeout_seconds: "
                        "must be a positive integer"
                    ),
                )
            )

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


def _result(
    *,
    profile: TestProfile,
    git_sha: str,
    checkout_sha: str,
    status: ProfileStatus,
    steps: tuple[StepResult, ...],
    reason: str,
    started_at: str,
) -> ProfileResult:
    repository, ref = _metadata()
    return ProfileResult(
        profile=profile.name,
        git_sha=git_sha.lower(),
        checkout_sha=checkout_sha.lower(),
        status=status,
        steps=steps,
        reason=reason,
        required_steps=profile.required_step_names,
        started_at=started_at,
        ended_at=_now(),
        repository=repository,
        ref=ref,
    )


def run_profile(
    profile: TestProfile,
    git_sha: str,
    *,
    executor: StepExecutor | None = None,
    cwd: Path | None = None,
    checkout_sha: str | None = None,
) -> ProfileResult:
    started_at = _now()
    actual_checkout_sha = checkout_sha or git_sha
    if _FULL_SHA.fullmatch(git_sha) is None:
        return _result(
            profile=profile,
            git_sha=git_sha,
            checkout_sha=actual_checkout_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason="git SHA must be an exact 40-character hexadecimal commit SHA",
            started_at=started_at,
        )
    if _FULL_SHA.fullmatch(actual_checkout_sha) is None:
        return _result(
            profile=profile,
            git_sha=git_sha,
            checkout_sha=actual_checkout_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason="checkout SHA must be an exact 40-character hexadecimal commit SHA",
            started_at=started_at,
        )
    if actual_checkout_sha.lower() != git_sha.lower():
        return _result(
            profile=profile,
            git_sha=git_sha,
            checkout_sha=actual_checkout_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason="checkout SHA does not match expected exact SHA",
            started_at=started_at,
        )
    contract_failures = _profile_contract_failures(profile)
    if contract_failures:
        return _result(
            profile=profile,
            git_sha=git_sha,
            checkout_sha=actual_checkout_sha,
            status=ProfileStatus.FAIL,
            steps=contract_failures,
            reason="profile contract is invalid",
            started_at=started_at,
        )

    def execute_with_cwd(step: TestStep) -> StepResult:
        return execute_step(step, cwd=cwd)

    selected_executor = executor if executor is not None else execute_with_cwd
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
    return _result(
        profile=profile,
        git_sha=git_sha,
        checkout_sha=actual_checkout_sha,
        status=status,
        steps=tuple(results),
        reason=reason,
        started_at=started_at,
    )


def _git_head() -> tuple[str, str | None]:
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return "", f"cannot resolve checkout SHA: {type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return "", f"cannot resolve checkout SHA: git rev-parse exited {completed.returncode}"
    return completed.stdout.strip(), None


def _resolve_git_sha(explicit_sha: str | None) -> tuple[str, str | None]:
    if explicit_sha is not None:
        return explicit_sha, None
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha, None
    return _git_head()


def _write_report(path: str | None, result: ProfileResult) -> str | None:
    if path is None:
        return None
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.to_json() + "\n", encoding="utf-8")
    return str(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=[profile.value for profile in ProfileName])
    parser.add_argument("--sha", dest="git_sha")
    parser.add_argument("--output")
    parser.add_argument("--verify-head", action="store_true")
    args = parser.parse_args()

    profile_name = ProfileName(args.profile)
    profile = PROFILE_DEFINITIONS[profile_name]
    git_sha, resolution_error = _resolve_git_sha(args.git_sha)
    checkout_sha = git_sha
    must_verify_head = args.verify_head or profile_name is ProfileName.POST_MERGE
    if must_verify_head:
        checkout_sha, head_error = _git_head()
        resolution_error = resolution_error or head_error
    if resolution_error is not None:
        started_at = _now()
        result = _result(
            profile=profile,
            git_sha=git_sha,
            checkout_sha=checkout_sha,
            status=ProfileStatus.FAIL,
            steps=(),
            reason=resolution_error,
            started_at=started_at,
        )
    else:
        result = run_profile(profile, git_sha, checkout_sha=checkout_sha)
    _write_report(args.output, result)
    print(result.to_json())
    return 0 if result.status is ProfileStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())