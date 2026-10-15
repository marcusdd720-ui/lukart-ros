"""Kernel mount topology admission for a trusted, synthetic linked worktree.

This verifies the mandatory Bubblewrap argv grammar and deny-by-default
behavior. It DOES NOT certify a real host's OS namespace isolation by itself.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.groq_builder_integration import (
    _require_kernel_git_boundary,
    _required_isolated_bwrap_prefix,
)

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux namespace policy")


def prepared(tmp_path: Path):
    repo = tmp_path / "task"
    repo.mkdir()
    gitdir = tmp_path / "common-git-metadata" / "worktrees" / "task"
    gitdir.mkdir(parents=True)
    (repo / ".git").write_text(f"gitdir: {gitdir}\n")
    scope = SimpleNamespace(worktree=repo)
    argv = _required_isolated_bwrap_prefix(scope) + (
        "/usr/bin/python3", "-c", "print('done')",
    )
    return scope, SimpleNamespace(arguments=argv)


def test_valid_profile_has_single_writable_workspace_with_masked_git(tmp_path):
    scope, plan = prepared(tmp_path)
    _require_kernel_git_boundary(plan, scope)
    args = plan.arguments
    assert args.count("--bind") == 1
    assert args.count("--ro-bind") == 4
    assert args.count("--ro-bind-try") == 1
    optional = args[args.index("--ro-bind-try"):args.index("--ro-bind-try") + 3]
    assert optional == ("--ro-bind-try", "/lib64", "/lib64")
    assert args.count("--unshare-all") == 1
    assert args.count("--cap-drop") == 1
    before_chdir = args[args.index("--chdir") - 3:args.index("--chdir")]
    assert ("--ro-bind", "/dev/null", "/workspace/.git") == before_chdir
    assert args[args.index("--bind") + 1] == str(scope.worktree.resolve())
    assert "--unshare-net" in args and "--unshare-pid" in args


@pytest.mark.parametrize("mutation", [
    lambda a: a.replace(("--ro-bind", "/dev/null", "/workspace/.git"), tuple()),
    lambda a: a[:a.index("--")] + ("--bind", "/", "/host")
              + a[a.index("--"):],
    lambda a: a.replace(("--bind",), ("--ro-bind",)),
    lambda a: a.replace(("--unshare-all",), tuple()),
    lambda a: a.replace(("--cap-drop", "ALL"), tuple()),
    lambda a: a.replace(("--ro-bind", "/usr", "/usr"),
                         ("--ro-bind", "/", "/")),
    lambda a: a.replace(("--chdir", "/workspace"),
                         ("--chdir", "/")),
    lambda a: a.replace(("--",), tuple()),
])
def test_refuse_alt_mount_grammar(tmp_path, mutation):
    scope, plan = prepared(tmp_path)
    argv = plan.arguments
    # Exact tuple replacement avoids a mutable object escaping the profile.
    class ReplaceableTuple(tuple):
        def replace(self, needle, replacement):
            for idx in range(len(self) - len(needle) + 1):
                if tuple(self[idx:idx + len(needle)]) == needle:
                    return self[:idx] + replacement + self[idx + len(needle):]
            raise AssertionError("fixture not found")
    plan.arguments = mutation(ReplaceableTuple(argv))
    with pytest.raises(NightShiftContractError, match="Git metadata mount"):
        _require_kernel_git_boundary(plan, scope)


def test_missing_git_marker_is_rejected(tmp_path):
    scope, plan = prepared(tmp_path)
    (scope.worktree / ".git").unlink()
    with pytest.raises(NightShiftContractError, match="metadata marker"):
        _require_kernel_git_boundary(plan, scope)


def test_symlinked_git_marker_is_rejected(tmp_path):
    scope, plan = prepared(tmp_path)
    marker = scope.worktree / ".git"
    content = marker.read_text()
    marker.unlink()
    secret = tmp_path / "secret-marker"
    secret.write_text(content)
    marker.symlink_to(secret)
    with pytest.raises(NightShiftContractError, match="metadata marker"):
        _require_kernel_git_boundary(plan, scope)


def test_gitdir_inside_writable_worktree_is_rejected(tmp_path):
    scope, plan = prepared(tmp_path)
    unsafe = scope.worktree / "private-git-data"
    unsafe.mkdir()
    (scope.worktree / ".git").write_text(f"gitdir: {unsafe}\n")
    with pytest.raises(NightShiftContractError, match="metadata must reside outside"):
        _require_kernel_git_boundary(plan, scope)


def test_empty_worker_command_is_rejected(tmp_path):
    scope, plan = prepared(tmp_path)
    plan.arguments = plan.arguments[:plan.arguments.index("--") + 1]
    with pytest.raises(NightShiftContractError, match="Git metadata mount"):
        _require_kernel_git_boundary(plan, scope)



def test_oversized_git_marker_is_rejected(tmp_path):
    scope, plan = prepared(tmp_path)
    (scope.worktree / ".git").write_bytes(b"gitdir: " + b"A" * 1024)
    with pytest.raises(NightShiftContractError, match="metadata marker"):
        _require_kernel_git_boundary(plan, scope)


def test_fifo_git_marker_is_refused_without_blocking(tmp_path):
    scope, plan = prepared(tmp_path)
    marker = scope.worktree / ".git"
    marker.unlink()
    os.mkfifo(marker)
    with pytest.raises(NightShiftContractError, match="metadata marker"):
        _require_kernel_git_boundary(plan, scope)



def test_linux_bwrap_kernel_mount_isolation_if_available(tmp_path):
    # This is actual mount-namespace evidence only on a host that has bwrap.
    # A skipped test is NOT host security admission.
    bwrap = shutil.which("bwrap")
    if not bwrap:
        pytest.skip("bwrap unavailable; no host mount proof on this runner")
    scope, plan = prepared(tmp_path)
    host_marker = scope.worktree / ".git"
    # /tmp is hidden by the worker tmpfs, so a secret located there proves
    # nothing about external common Git metadata. Use a different host path.
    with tempfile.TemporaryDirectory(prefix="ros-git-proof-", dir="/var/tmp") as outside:
        host_gitdir = Path(outside) / "worktrees" / "task"
        host_gitdir.mkdir(parents=True)
        host_marker.write_text(f"gitdir: {host_gitdir}\\n")
        before = host_marker.read_bytes()
        secret = host_gitdir / "inaccessible"
        secret.write_text("original")
        argv = _required_isolated_bwrap_prefix(scope)
        _require_kernel_git_boundary(SimpleNamespace(arguments=argv + ("/usr/bin/python3",)), scope)
        script = (
            "import sys\\n"
            "from pathlib import Path\\n"
            "marker=Path('/workspace/.git')\\n"
            "assert marker.read_bytes()==b''\\n"
            "assert not Path(sys.argv[1]).exists(), 'host gitdir is mounted'\\n"
            "try:\\n"
            "    marker.write_bytes(b'tamper')\\n"
            "except OSError:\\n"
            "    pass\\n"
            "else:\\n"
            "    raise AssertionError('metadata file writable')\\n"
            "Path('/workspace/allowed.py').write_text('allowed')\\n"
        )
        result = subprocess.run(
            [bwrap, *argv, "/usr/bin/python3", "-c", script, str(host_gitdir)],
            check=False, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert host_marker.read_bytes() == before
        assert secret.read_text() == "original"
        assert (scope.worktree / "allowed.py").read_text() == "allowed"


def test_invalid_mount_rejected_before_credential_read(tmp_path, monkeypatch):
    from core.night_shift import groq_builder_integration as integration

    scope, plan = prepared(tmp_path)
    scope.task_id = "task"
    scope.base_sha = "a" * 40
    plan.role = "BUILDER"
    plan.task_id = "task"
    plan.worktree = scope.worktree
    plan.base_sha = scope.base_sha
    plan.executable = Path("/usr/bin/bwrap")
    index = plan.arguments.index("--")
    plan.arguments = (
        plan.arguments[:index]
        + ("--bind", "/", "/escape")
        + plan.arguments[index:]
    )

    class BrokerPolicy:
        task_id = "task"

    def forbidden_secret(_path):
        raise AssertionError("credential must not load before mount admission")
    monkeypatch.setattr(integration, "read_groq_key", forbidden_secret)
    with pytest.raises(NightShiftContractError, match="Git metadata mount"):
        integration.run_scoped_builder(
            leases=None, journal=None, plan=plan, scope=scope,
            broker_policy=BrokerPolicy(), auth_file=tmp_path / "secret",
            broker_socket=tmp_path / "private.sock",
            pinned_launch_arguments_sha256=hashlib.sha256(
                "\0".join(plan.arguments).encode()
            ).hexdigest(),
            trusted_admission_checker=lambda _plan: True,
        )

def test_socket_inside_writable_workspace_rejected_without_secret(tmp_path, monkeypatch):
    from core.night_shift import groq_builder_integration as integration

    scope, plan = prepared(tmp_path)
    scope.task_id = "task"
    scope.base_sha = "a" * 40
    plan.role = "BUILDER"
    plan.task_id = "task"
    plan.worktree = scope.worktree
    plan.base_sha = scope.base_sha
    plan.executable = Path("/usr/bin/bwrap")

    class BrokerPolicy:
        task_id = "task"

    def forbidden_secret(_path):
        raise AssertionError("credential must not load before mount admission")

    monkeypatch.setattr(integration, "read_groq_key", forbidden_secret)
    with pytest.raises(NightShiftContractError, match="outside writable worker mount"):
        integration.run_scoped_builder(
            leases=None, journal=None, plan=plan, scope=scope,
            broker_policy=BrokerPolicy(), auth_file=tmp_path / "secret",
            broker_socket=scope.worktree / "private.sock",
            pinned_launch_arguments_sha256=hashlib.sha256(
                "\0".join(plan.arguments).encode()
            ).hexdigest(),
            trusted_admission_checker=lambda _plan: True,
        )
