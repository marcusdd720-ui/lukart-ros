"""Fail-closed admission preflight for the existing child process bridge composition."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.groq_builder_integration import run_scoped_builder
from core.night_shift.groq_builder_scope import ApprovedBuilderScope
from core.night_shift.groq_local_broker import GroqBrokerPolicy


def rig(tmp_path):
    worktree = tmp_path / 'private-isolated-repo'
    worktree.mkdir()
    task_id = 'TASK-INTEGRATION'
    base = '1' * 40
    args = ('--unshare-net', '--unshare-pid', '--cap-drop', 'ALL', '--clearenv',
            '--ro-bind', '/usr', '/usr')
    plan = SimpleNamespace(role='BUILDER', task_id=task_id, worktree=worktree,
                           base_sha=base, executable=Path('/usr/bin/bwrap'), arguments=args)
    scope = ApprovedBuilderScope(task_id=task_id, worktree=worktree,
                                 branch='night-shift/isolated-task', base_sha=base,
                                 allowed_files=('module.py',))
    policy = GroqBrokerPolicy(task_id=task_id, task_marker='TASK_INTEGRATION_MARKER_1')
    return dict(leases=None, journal=None, plan=plan, scope=scope, broker_policy=policy,
                auth_file=tmp_path / 'no-key', broker_socket=tmp_path / 'sock',
                pinned_launch_arguments_sha256=hashlib.sha256('\0'.join(args).encode()).hexdigest(),
                trusted_admission_checker=lambda candidate: True)


def test_no_untrusted_host_implicit_admission(tmp_path):
    kwargs = rig(tmp_path)
    kwargs['trusted_admission_checker'] = None
    with pytest.raises(NightShiftContractError, match='trusted host'):
        run_scoped_builder(**kwargs)


def test_rejects_scope_substitution_before_loading_secret(tmp_path):
    kwargs = rig(tmp_path)
    kwargs['plan'].task_id = 'DIFFERENT'
    with pytest.raises(NightShiftContractError, match='approved scope'):
        run_scoped_builder(**kwargs)


def test_rejects_non_pinned_bwrap_argv_before_loading_secret(tmp_path):
    kwargs = rig(tmp_path)
    kwargs['plan'].arguments = ('--unshare-net',)
    with pytest.raises(NightShiftContractError, match='argv differs'):
        run_scoped_builder(**kwargs)


def test_rejects_non_bwrap_binary_before_loading_secret(tmp_path):
    kwargs = rig(tmp_path)
    kwargs['plan'].executable = Path('/usr/bin/sh')
    with pytest.raises(NightShiftContractError, match='bubblewrap'):
        run_scoped_builder(**kwargs)


def test_rejects_missing_kernel_isolation_before_loading_secret(tmp_path):
    kwargs = rig(tmp_path)
    args = ('--clearenv', '--ro-bind', '/usr', '/usr')
    kwargs['plan'].arguments = args
    kwargs['pinned_launch_arguments_sha256'] = hashlib.sha256('\0'.join(args).encode()).hexdigest()
    with pytest.raises(NightShiftContractError, match='namespace'):
        run_scoped_builder(**kwargs)


@pytest.mark.parametrize('arguments', [
    ('--unshare-net', '--unshare-pid', '--cap-drop', 'CAP_NET_ADMIN',
     'ALL', '--clearenv'),
    ('--unshare-net', '--unshare-pid', '--cap-drop',
     '--clearenv', 'ALL'),
    ('--unshare-net', '--unshare-pid', '--cap-drop', 'ALL',
     '--cap-add', 'CAP_NET_ADMIN', '--clearenv'),
    ('--unshare-net', '--unshare-pid', '--cap-drop', 'ALL',
     '--share-net', '--clearenv'),
    ('--unshare-net', '--unshare-pid', '--cap-drop', 'ALL',
     '--cap-drop', 'CAP_NET_ADMIN', '--clearenv'),
])
def test_rejects_nonadjacent_or_overridden_cap_drop(tmp_path, arguments):
    kwargs = rig(tmp_path)
    kwargs['plan'].arguments = arguments
    kwargs['pinned_launch_arguments_sha256'] = hashlib.sha256(
        '\0'.join(arguments).encode()
    ).hexdigest()
    with pytest.raises(NightShiftContractError, match='namespace'):
        run_scoped_builder(**kwargs)
