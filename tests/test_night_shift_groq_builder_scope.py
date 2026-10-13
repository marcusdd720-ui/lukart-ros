"""Bounded postflight checks for actual isolated Git worktree changes."""
from __future__ import annotations

import subprocess
from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.groq_builder_scope import ApprovedBuilderScope, verify_builder_changes


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


@pytest.fixture()
def fixture(tmp_path):
    git(tmp_path, 'init', '-q')
    (tmp_path / 'baseline.txt').write_text('baseline', encoding='utf8')
    git(tmp_path, 'add', 'baseline.txt')
    subprocess.check_call(['git', '-C', str(tmp_path), '-c', 'user.name=Test',
                           '-c', 'user.email=test@invalid', 'commit', '-qm', 'baseline'])
    git(tmp_path, 'checkout', '-qb', 'night-shift/builder')
    scope = ApprovedBuilderScope(task_id='task', worktree=tmp_path,
                                 branch='night-shift/builder',
                                 base_sha=git(tmp_path, 'rev-parse', 'HEAD'),
                                 allowed_files=('safe.py',))
    return tmp_path, scope


def test_accept_exact_created_file(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('result = 2 + 3\n')
    proof = verify_builder_changes(scope)
    assert len(proof['safe.py']) == 64


def test_refuse_unchanged(fixture):
    _, scope = fixture
    with pytest.raises(NightShiftContractError, match='change count'):
        verify_builder_changes(scope)


def test_refuse_other_file(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('approved')
    (root / 'private.txt').write_text('unapproved')
    with pytest.raises(NightShiftContractError, match='unapproved'):
        verify_builder_changes(scope)


def test_refuse_ignored_untracked_file(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('approved')
    # Keep the ignore rule in Git metadata, not in an extra unapproved file.
    (root / '.git' / 'info' / 'exclude').write_text('hidden.dat\n')
    (root / 'hidden.dat').write_text('unexpected')
    ignored_view = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z']
    )
    all_view = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--others', '-z']
    )
    assert b'hidden.dat\0' not in ignored_view
    assert b'hidden.dat\0' in all_view
    with pytest.raises(NightShiftContractError, match='unapproved'):
        verify_builder_changes(scope)



def test_rejects_newline_prefixed_untracked_path_even_with_allowed_twin(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('approved')
    (root / '\nsafe.py').write_text('unapproved')
    with pytest.raises(NightShiftContractError, match='unapproved'):
        verify_builder_changes(scope)


def test_refuse_staged_rename_hiding_deleted_tracked_file(fixture):
    root, scope = fixture
    # The only allowed target is safe.py; baseline.txt deletion is forbidden.
    (root / 'baseline.txt').rename(root / 'safe.py')
    git(root, 'add', '-A')
    git(root, 'config', 'diff.renames', 'true')
    with pytest.raises(NightShiftContractError, match='unapproved'):
        verify_builder_changes(scope)


def test_refuse_symlink(fixture):
    root, scope = fixture
    (root / 'safe.py').symlink_to('baseline.txt')
    with pytest.raises(NightShiftContractError, match='unsafe modified file'):
        verify_builder_changes(scope)


def test_refuse_deletion(fixture):
    root, scope = fixture
    (root / 'baseline.txt').unlink()
    with pytest.raises(NightShiftContractError, match='unapproved'):
        verify_builder_changes(scope)


def test_refuse_branch_change(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('approved')
    git(root, 'checkout', '-qb', 'main')
    with pytest.raises(NightShiftContractError, match='branch changed'):
        verify_builder_changes(scope)


def test_refuse_commit_drift(fixture):
    root, scope = fixture
    (root / 'safe.py').write_text('approved')
    git(root, 'add', 'safe.py')
    subprocess.check_call(['git', '-C', str(root), '-c', 'user.name=Test',
                           '-c', 'user.email=test@invalid', 'commit', '-qm', 'drift'])
    with pytest.raises(NightShiftContractError, match='base SHA changed'):
        verify_builder_changes(scope)


@pytest.mark.parametrize(
    'name', ['/tmp/e', '../bad', '.git/config', 'new\\file', '.internal', 'x/../y']
)
def test_disallow_unsafe_scope_paths(fixture, name):
    _, scope = fixture
    with pytest.raises(NightShiftContractError, match='unsafe'):
        replace(scope, allowed_files=(name,))
