import json
import subprocess
import sys
from pathlib import Path

import pytest

import factory.quality.test_profiles as profiles
from factory.quality.test_profiles import (
    ProfileName,
    ProfileStatus,
    StepResult,
    StepStatus,
    execute_step,
    run_profile,
)
from factory.quality.test_profiles import (
    TestProfile as ProfileDefinition,
)
from factory.quality.test_profiles import (
    TestStep as ProfileStep,
)

SHA = "69f4843be7fc94c446f72b891a8fb44fbf9d9ed3"


def _profile(*steps: ProfileStep, required: tuple[str, ...] | None = None) -> ProfileDefinition:
    required_names = required if required is not None else tuple(step.name for step in steps)
    return ProfileDefinition(name=ProfileName.FAST, steps=steps, required_step_names=required_names)


def _result(
    step: ProfileStep,
    status: StepStatus,
    exit_code: int | None = 0,
    reason: str = "ok",
) -> StepResult:
    return StepResult(
        name=step.name,
        command=step.command,
        required=step.required,
        status=status,
        exit_code=exit_code,
        reason=reason,
    )


def test_profile_passes_only_when_all_required_steps_pass() -> None:
    steps = (ProfileStep("one", ("python", "-V")), ProfileStep("two", ("python", "-V")))
    result = run_profile(
        _profile(*steps),
        SHA,
        executor=lambda step: _result(step, StepStatus.PASS),
    )

    assert result.status is ProfileStatus.PASS
    assert [step.status for step in result.steps] == [StepStatus.PASS, StepStatus.PASS]


def test_non_zero_exit_code_fails_required_step() -> None:
    step = ProfileStep("failing", ("python", "-c", "raise SystemExit(7)"))
    result = run_profile(_profile(step), SHA)

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert result.steps[0].exit_code == 7
    assert "exit code 7" in result.steps[0].reason


def test_missing_command_fails_required_step() -> None:
    step = ProfileStep("missing", ("__case_testy_missing_command__",))
    result = run_profile(_profile(step), SHA)

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert result.steps[0].exit_code is None
    assert "missing command" in result.steps[0].reason


def test_executor_exception_fails_required_step() -> None:
    step = ProfileStep("exception", ("python", "-V"))

    def explode(_: ProfileStep) -> StepResult:
        raise RuntimeError("synthetic executor failure")

    result = run_profile(_profile(step), SHA, executor=explode)

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert "RuntimeError" in result.steps[0].reason


def test_unknown_is_promoted_to_fail_for_required_step() -> None:
    step = ProfileStep("unknown", ("python", "-V"))
    result = run_profile(
        _profile(step),
        SHA,
        executor=lambda item: _result(item, StepStatus.UNKNOWN, exit_code=None, reason="unknown"),
    )

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert "UNKNOWN" in result.steps[0].reason


def test_one_failed_required_step_prevents_false_pass() -> None:
    steps = (ProfileStep("pass", ("python", "-V")), ProfileStep("fail", ("python", "-V")))

    def execute(step: ProfileStep) -> StepResult:
        status = StepStatus.FAIL if step.name == "fail" else StepStatus.PASS
        code = 1 if status is StepStatus.FAIL else 0
        return _result(step, status, exit_code=code, reason="synthetic")

    result = run_profile(_profile(*steps), SHA, executor=execute)

    assert result.status is ProfileStatus.FAIL
    assert any(step.required and step.status is not StepStatus.PASS for step in result.steps)


def test_executor_cannot_fake_pass_with_non_zero_exit_code() -> None:
    step = ProfileStep("liar", ("python", "-V"))
    result = run_profile(
        _profile(step),
        SHA,
        executor=lambda item: _result(
            item, StepStatus.PASS, exit_code=9, reason="synthetic false pass"
        ),
    )

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert "invalid PASS" in result.steps[0].reason


def test_profile_with_no_required_steps_fails_closed() -> None:
    profile = ProfileDefinition(name=ProfileName.FAST, steps=(), required_step_names=())
    result = run_profile(profile, SHA)

    assert result.status is ProfileStatus.FAIL
    assert result.steps[0].status is StepStatus.FAIL
    assert "no required steps" in result.steps[0].reason


def test_steps_execute_in_declared_order() -> None:
    steps = tuple(ProfileStep(name, ("python", "-V")) for name in ("first", "second", "third"))
    seen: list[str] = []

    def execute(step: ProfileStep) -> StepResult:
        seen.append(step.name)
        return _result(step, StepStatus.PASS)

    result = run_profile(_profile(*steps), SHA, executor=execute)

    assert result.status is ProfileStatus.PASS
    assert seen == ["first", "second", "third"]
    assert [step.name for step in result.steps] == seen


def test_result_contains_profile_and_exact_sha() -> None:
    result = run_profile(
        _profile(ProfileStep("one", ("python", "-V"))),
        SHA,
        executor=lambda step: _result(step, StepStatus.PASS),
    )

    assert result.profile is ProfileName.FAST
    assert result.git_sha == SHA


def test_missing_required_step_fails_profile_contract() -> None:
    profile = _profile(ProfileStep("present", ("python", "-V")), required=("present", "missing"))
    result = run_profile(profile, SHA, executor=lambda step: _result(step, StepStatus.PASS))

    assert result.status is ProfileStatus.FAIL
    missing = [step for step in result.steps if step.name == "missing"]
    assert len(missing) == 1
    assert missing[0].status is StepStatus.FAIL
    assert "required step missing" in missing[0].reason


def test_result_is_machine_readable_json() -> None:
    result = run_profile(
        _profile(ProfileStep("one", ("python", "-V"))),
        SHA,
        executor=lambda step: _result(step, StepStatus.PASS),
    )
    payload = json.loads(result.to_json())

    assert payload["profile"] == "FAST"
    assert payload["git_sha"] == SHA
    assert payload["status"] == "PASS"
    assert payload["steps"][0]["status"] == "PASS"


@pytest.mark.parametrize("profile_name", list(ProfileName))
def test_all_supported_profiles_have_explicit_required_steps(profile_name: ProfileName) -> None:
    from factory.quality.test_profiles import PROFILE_DEFINITIONS

    profile = PROFILE_DEFINITIONS[profile_name]
    names = tuple(step.name for step in profile.steps)

    assert profile.required_step_names
    assert all(required in names for required in profile.required_step_names)


def test_invalid_sha_fails_closed_without_executing_steps() -> None:
    called = False

    def execute(step: ProfileStep) -> StepResult:
        nonlocal called
        called = True
        return _result(step, StepStatus.PASS)

    result = run_profile(
        _profile(ProfileStep("one", ("python", "-V"))),
        "69f4843",
        executor=execute,
    )

    assert result.status is ProfileStatus.FAIL
    assert "40-character" in result.reason
    assert called is False

def test_execute_step_propagates_timeout_to_bounded_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_bounded(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["cwd"] = cwd
        seen["timeout"] = timeout_seconds
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(profiles, "_run_bounded_process", fake_bounded)

    step = ProfileStep(
        "bounded",
        ("python", "-V"),
        timeout_seconds=17,
    )
    result = execute_step(step)

    assert result.status is StepStatus.PASS
    assert result.exit_code == 0
    assert seen["timeout"] == 17
    command = seen["command"]
    assert isinstance(command, tuple)
    assert command[0] == sys.executable


def test_execute_step_timeout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_bounded(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        del command, cwd
        raise profiles._BoundedProcessTimeout(
            timeout_seconds,
            tree_terminated=True,
        )

    monkeypatch.setattr(profiles, "_run_bounded_process", fake_bounded)

    step = ProfileStep(
        "slow",
        ("python", "-V"),
        timeout_seconds=3,
    )
    result = execute_step(step)

    assert result.status is StepStatus.FAIL
    assert result.exit_code is None
    assert result.reason == "timeout after 3s"


def test_posix_process_launch_uses_isolated_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class FakeProcess:
        pass

    def fake_popen(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(profiles, "_IS_WINDOWS", False)
    monkeypatch.setattr(profiles.subprocess, "Popen", fake_popen)

    profiles._start_process(("python", "-V"), cwd=None)

    assert seen["start_new_session"] is True
    assert "creationflags" not in seen


def test_windows_process_launch_uses_new_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class FakeProcess:
        pass

    def fake_popen(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(profiles, "_IS_WINDOWS", True)
    monkeypatch.setattr(profiles.subprocess, "Popen", fake_popen)

    profiles._start_process(("python", "-V"), cwd=None)

    assert seen["creationflags"] == profiles._WINDOWS_NEW_PROCESS_GROUP
    assert "start_new_session" not in seen


def test_bounded_timeout_invokes_tree_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled: list[int] = []

    class FakeProcess:
        pid = 731
        returncode = None

        def communicate(self, *, timeout: int):
            raise subprocess.TimeoutExpired(cmd=("python", "-V"), timeout=timeout)

    process = FakeProcess()

    monkeypatch.setattr(profiles, "_start_process", lambda *args, **kwargs: process)

    def fake_terminate(item) -> bool:
        assert item is process
        cancelled.append(item.pid)
        return True

    monkeypatch.setattr(profiles, "_terminate_process_tree", fake_terminate)

    with pytest.raises(profiles._BoundedProcessTimeout) as caught:
        profiles._run_bounded_process(
            ("python", "-V"),
            cwd=None,
            timeout_seconds=2,
        )

    assert cancelled == [731]
    assert caught.value.tree_terminated is True


def test_posix_tree_termination_reaps_direct_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signals: list[tuple[int, int]] = []
    waits: list[int] = []

    class FakeProcess:
        pid = 991

        def poll(self) -> int | None:
            return 0

        def wait(self, *, timeout: float | None = None) -> int:
            assert timeout is not None
            waits.append(int(timeout))
            return 0

        def terminate(self) -> None:
            raise AssertionError("fallback terminate should not run")

        def kill(self) -> None:
            raise AssertionError("fallback kill should not run")

    monkeypatch.setattr(profiles, "_IS_WINDOWS", False)
    monkeypatch.setattr(profiles.signal, "SIGTERM", 15, raising=False)
    monkeypatch.setattr(profiles.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(
        profiles.os,
        "killpg",
        lambda pid, sig: signals.append((pid, sig)),
        raising=False,
    )

    assert profiles._terminate_process_tree(FakeProcess()) is True
    assert signals == [
        (991, 15),
        (991, 9),
    ]
    assert waits == [profiles.PROCESS_TREE_TERMINATION_GRACE_SECONDS]


def test_git_head_uses_explicit_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_bounded(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["cwd"] = cwd
        seen["timeout"] = timeout_seconds
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=SHA + "\n",
            stderr="",
        )

    monkeypatch.setattr(profiles, "_run_bounded_process", fake_bounded)

    head, error = profiles._git_head()

    assert head == SHA
    assert error is None
    assert seen["command"] == ("git", "rev-parse", "HEAD")
    assert seen["timeout"] == profiles.GIT_HEAD_TIMEOUT_SECONDS


def test_git_head_timeout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_bounded(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        del command, cwd
        raise profiles._BoundedProcessTimeout(
            timeout_seconds,
            tree_terminated=True,
        )

    monkeypatch.setattr(profiles, "_run_bounded_process", fake_bounded)

    head, error = profiles._git_head()

    assert head == ""
    assert error == (
        "cannot resolve checkout SHA: "
        f"timeout after {profiles.GIT_HEAD_TIMEOUT_SECONDS}s"
    )

def test_non_positive_timeout_fails_profile_contract() -> None:
    called = False

    def execute(step: ProfileStep) -> StepResult:
        nonlocal called
        called = True
        return _result(
            step,
            StepStatus.PASS,
        )

    step = ProfileStep(
        "invalid-budget",
        ("python", "-V"),
        timeout_seconds=0,
    )

    result = run_profile(
        _profile(step),
        SHA,
        executor=execute,
    )

    assert result.status is ProfileStatus.FAIL
    assert called is False
    assert result.steps[0].status is StepStatus.FAIL
    assert (
        result.steps[0].reason
        == (
            "invalid timeout_seconds: "
            "must be a positive integer"
        )
    )


def test_case_testy_post_merge_has_job_watchdog() -> None:
    workflow = Path(
        ".github/workflows/"
        "case-testy-post-merge.yml"
    ).read_text(encoding="utf-8")

    expected = (
        "  case-testy-post-merge:\n"
        "    name: case-testy-post-merge\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 20\n"
    )

    assert expected in workflow
