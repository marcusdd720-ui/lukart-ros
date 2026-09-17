from __future__ import annotations

import base64
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

from factory.github_actions_client import (
    CommitOnBranchResult,
    GitHubActionsClient,
    GitHubActionsError,
)
from factory.quality import case_signed_authoring_hardened as hardened


def _manifest(
    *,
    tmp_path: Path,
    expected_head: str = "a" * 40,
) -> tuple[hardened.AuthoringManifest, Path, dict[str, str]]:
    contents = {
        path: f"synthetic:{path}\n"
        for path in sorted(hardened.ALLOWED_PATHS)
    }

    for path, text in contents.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    files = tuple(
        (
            path,
            hardened.sha256_text(contents[path]),
        )
        for path in sorted(contents)
    )

    tree_digest = hardened.canonical_tree_digest(contents)

    manifest = hardened.AuthoringManifest(
        schema_version=hardened.MANIFEST_SCHEMA,
        operation_id=hardened.operation_identity(
            repository="example/project",
            base_branch=hardened.MAIN_BRANCH,
            target_branch=hardened.TARGET_BRANCH,
            expected_head_sha=expected_head,
            tree_digest=tree_digest,
            files=files,
        ),
        operation=hardened.OPERATION,
        repository="example/project",
        base_branch=hardened.MAIN_BRANCH,
        target_branch=hardened.TARGET_BRANCH,
        expected_head_sha=expected_head,
        tree_digest=tree_digest,
        files=files,
    )

    manifest.validate()

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            manifest.to_dict(),
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return manifest, manifest_path, contents


def _commit(
    manifest: hardened.AuthoringManifest,
    sha: str,
    *,
    verified: bool = True,
    reason: str = "valid",
) -> dict[str, Any]:
    return {
        "sha": sha,
        "commit": {
            "message": (
                "synthetic\n\n"
                f"LUKART-Operation-ID: {manifest.operation_id}"
            ),
            "verification": {
                "verified": verified,
                "reason": reason,
            },
        },
        "parents": [
            {
                "sha": manifest.expected_head_sha,
            }
        ],
    }


def _stub_local_publish_state(
    monkeypatch: pytest.MonkeyPatch,
    manifest: hardened.AuthoringManifest,
) -> None:
    monkeypatch.setenv(
        "GITHUB_REPOSITORY",
        manifest.repository,
    )

    monkeypatch.setattr(
        hardened,
        "working_tree_paths",
        lambda repo_root: set(hardened.ALLOWED_PATHS),
    )

    monkeypatch.setattr(
        hardened,
        "git_head",
        lambda repo_root: manifest.expected_head_sha,
    )


class FakeClient:
    repository = "example/project"

    def __init__(
        self,
        manifest: hardened.AuthoringManifest,
        contents: dict[str, str],
    ) -> None:
        self.manifest = manifest
        self.contents = contents
        self.base_head = manifest.expected_head_sha
        self.target_head: str | None = None
        self.resulting_sha = "b" * 40
        self.created_commits = 0
        self.created_refs = 0
        self.created_prs = 0
        self.pr: dict[str, Any] | None = None

    def get_ref_or_none(
        self,
        branch: str,
    ) -> dict[str, Any] | None:
        if branch == self.manifest.target_branch:
            if self.target_head is None:
                return None

            return {
                "ref": f"refs/heads/{branch}",
                "object": {
                    "sha": self.target_head,
                },
            }

        if branch == self.manifest.base_branch:
            return {
                "ref": f"refs/heads/{branch}",
                "object": {
                    "sha": self.base_head,
                },
            }

        raise AssertionError(branch)

    def get_ref_sha(
        self,
        branch: str,
    ) -> str:
        if branch == self.manifest.base_branch:
            return self.base_head

        if (
            branch == self.manifest.target_branch
            and self.target_head is not None
        ):
            return self.target_head

        raise AssertionError(branch)

    def create_ref(
        self,
        branch: str,
        sha: str,
    ) -> dict[str, Any]:
        assert branch == self.manifest.target_branch
        assert sha == self.manifest.expected_head_sha

        self.created_refs += 1
        self.target_head = sha

        return {
            "ref": f"refs/heads/{branch}",
            "object": {
                "sha": sha,
            },
        }

    def create_commit_on_branch(
        self,
        *,
        branch: str,
        expected_head_oid: str,
        message_headline: str,
        additions: dict[str, str],
        deletions: tuple[str, ...] = (),
        operation_id: str | None = None,
        message_body: str | None = None,
    ) -> CommitOnBranchResult:
        assert branch == self.manifest.target_branch
        assert expected_head_oid == self.manifest.expected_head_sha
        assert message_headline
        assert additions == self.contents
        assert deletions == ()
        assert operation_id == self.manifest.operation_id
        assert message_body is not None
        assert self.manifest.operation_id in message_body

        self.created_commits += 1
        self.target_head = self.resulting_sha

        return CommitOnBranchResult(
            commit_oid=self.resulting_sha,
            ref_name=f"refs/heads/{branch}",
            ref_oid=self.resulting_sha,
            url=(
                "https://example.invalid/commit/"
                f"{self.resulting_sha}"
            ),
            client_mutation_id=operation_id,
        )

    def get_commit(
        self,
        sha: str,
    ) -> dict[str, Any]:
        assert sha == self.resulting_sha

        return _commit(
            self.manifest,
            sha,
        )

    def compare_commits(
        self,
        base: str,
        head: str,
    ) -> dict[str, Any]:
        assert base == self.manifest.expected_head_sha
        assert head == self.resulting_sha

        return {
            "ahead_by": 1,
            "total_commits": 1,
            "files": [
                {
                    "filename": path,
                }
                for path in sorted(hardened.ALLOWED_PATHS)
            ],
        }

    def _api(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del body

        assert method == "GET"

        prefix = (
            f"/repos/{self.repository}/contents/"
        )

        assert path.startswith(prefix)

        encoded = path[len(prefix):].split(
            "?ref=",
            1,
        )[0]

        file_path = urllib.parse.unquote(encoded)

        return {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(
                self.contents[file_path].encode("utf-8")
            ).decode("ascii"),
        }

    def list_open_pull_requests(
        self,
        *,
        head_branch: str | None = None,
        base_branch: str | None = None,
    ) -> list[dict[str, Any]]:
        assert head_branch == self.manifest.target_branch
        assert base_branch == self.manifest.base_branch

        if self.pr is None:
            return []

        return [self.pr]

    def create_pull_request(
        self,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> dict[str, Any]:
        assert title
        assert body
        assert head == self.manifest.target_branch
        assert base == self.manifest.base_branch

        self.created_prs += 1

        self.pr = {
            "number": 123,
            "html_url": "https://example.invalid/pr/123",
            "head": {
                "ref": self.manifest.target_branch,
                "sha": self.resulting_sha,
            },
            "base": {
                "ref": self.manifest.base_branch,
                "sha": self.manifest.expected_head_sha,
            },
        }

        return self.pr


def test_validation_environment_removes_write_secrets() -> None:
    env = hardened.validation_environment(
        {
            "LUKART_ROS_FACTORY_PRIVATE_KEY": "secret",
            "GITHUB_TOKEN": "token",
            "GH_TOKEN": "gh-token",
            "SAFE_VALUE": "ok",
        }
    )

    assert "LUKART_ROS_FACTORY_PRIVATE_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "GH_TOKEN" not in env
    assert env["SAFE_VALUE"] == "ok"


def test_manifest_rejects_direct_main_publication(
    tmp_path: Path,
) -> None:
    manifest, _, _ = _manifest(
        tmp_path=tmp_path
    )

    unsafe = hardened.AuthoringManifest(
        schema_version=manifest.schema_version,
        operation_id=manifest.operation_id,
        operation=manifest.operation,
        repository=manifest.repository,
        base_branch=manifest.base_branch,
        target_branch="main",
        expected_head_sha=manifest.expected_head_sha,
        tree_digest=manifest.tree_digest,
        files=manifest.files,
    )

    with pytest.raises(
        hardened.SignedAuthoringHardeningError,
    ):
        unsafe.validate()


def test_manifest_operation_id_is_bound_to_inputs(
    tmp_path: Path,
) -> None:
    manifest, _, _ = _manifest(
        tmp_path=tmp_path
    )

    invalid = hardened.AuthoringManifest(
        schema_version=manifest.schema_version,
        operation_id="case-testy-author-invalid",
        operation=manifest.operation,
        repository=manifest.repository,
        base_branch=manifest.base_branch,
        target_branch=manifest.target_branch,
        expected_head_sha=manifest.expected_head_sha,
        tree_digest=manifest.tree_digest,
        files=manifest.files,
    )

    with pytest.raises(
        hardened.SignedAuthoringHardeningError,
        match="operation_id",
    ):
        invalid.validate()


def test_validated_bytes_change_blocks_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_path, contents = _manifest(
        tmp_path=tmp_path
    )

    _stub_local_publish_state(
        monkeypatch,
        manifest,
    )

    path = next(
        iter(hardened.ALLOWED_PATHS)
    )

    (tmp_path / path).write_text(
        "tampered\n",
        encoding="utf-8",
    )

    client = FakeClient(
        manifest,
        contents,
    )

    with pytest.raises(
        hardened.SignedAuthoringHardeningError,
        match="validated bytes changed",
    ):
        hardened.publish_operation(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            client=client,  # type: ignore[arg-type]
        )


def test_base_sha_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_path, contents = _manifest(
        tmp_path=tmp_path
    )

    _stub_local_publish_state(
        monkeypatch,
        manifest,
    )

    client = FakeClient(
        manifest,
        contents,
    )

    client.base_head = "c" * 40

    with pytest.raises(
        hardened.StaleAuthoringOperation,
        match="base moved",
    ):
        hardened.publish_operation(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            client=client,  # type: ignore[arg-type]
        )

    assert client.created_refs == 0
    assert client.created_commits == 0
    assert client.created_prs == 0


def test_publish_is_one_atomic_verified_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_path, contents = _manifest(
        tmp_path=tmp_path
    )

    _stub_local_publish_state(
        monkeypatch,
        manifest,
    )

    client = FakeClient(
        manifest,
        contents,
    )

    receipt = hardened.publish_operation(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        client=client,  # type: ignore[arg-type]
    )

    assert client.created_refs == 1
    assert client.created_commits == 1
    assert client.created_prs == 1

    assert (
        receipt["resulting_sha"]
        == client.resulting_sha
    )

    assert (
        receipt["publication"]
        == "VERIFIED"
    )

    assert (
        receipt["signature"]
        == "VERIFIED"
    )

    assert (
        receipt["ci"]
        == "PENDING_EXACT_SHA"
    )


def test_retry_reconciles_without_duplicate_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_path, contents = _manifest(
        tmp_path=tmp_path
    )

    _stub_local_publish_state(
        monkeypatch,
        manifest,
    )

    client = FakeClient(
        manifest,
        contents,
    )

    client.target_head = (
        client.resulting_sha
    )

    client.pr = {
        "number": 123,
        "html_url": "https://example.invalid/pr/123",
        "head": {
            "ref": manifest.target_branch,
            "sha": client.resulting_sha,
        },
        "base": {
            "ref": manifest.base_branch,
            "sha": manifest.expected_head_sha,
        },
    }

    receipt = hardened.publish_operation(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        client=client,  # type: ignore[arg-type]
    )

    assert client.created_refs == 0
    assert client.created_commits == 0
    assert client.created_prs == 0

    assert (
        receipt["resulting_sha"]
        == client.resulting_sha
    )


def test_ambiguous_write_reconciles_before_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_path, contents = _manifest(
        tmp_path=tmp_path
    )

    _stub_local_publish_state(
        monkeypatch,
        manifest,
    )

    class AmbiguousClient(FakeClient):
        def create_commit_on_branch(
            self,
            *,
            branch: str,
            expected_head_oid: str,
            message_headline: str,
            additions: dict[str, str],
            deletions: tuple[str, ...] = (),
            operation_id: str | None = None,
            message_body: str | None = None,
        ) -> CommitOnBranchResult:
            super().create_commit_on_branch(
                branch=branch,
                expected_head_oid=expected_head_oid,
                message_headline=message_headline,
                additions=additions,
                deletions=deletions,
                operation_id=operation_id,
                message_body=message_body,
            )

            raise GitHubActionsError(
                "synthetic ambiguous transport failure"
            )

    client = AmbiguousClient(
        manifest,
        contents,
    )

    receipt = hardened.publish_operation(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        client=client,  # type: ignore[arg-type]
    )

    assert client.created_commits == 1

    assert (
        receipt["resulting_sha"]
        == client.resulting_sha
    )


def test_unsigned_result_is_rejected(
    tmp_path: Path,
) -> None:
    manifest, _, contents = _manifest(
        tmp_path=tmp_path
    )

    class UnsignedClient(FakeClient):
        def get_commit(
            self,
            sha: str,
        ) -> dict[str, Any]:
            assert sha == self.resulting_sha

            return _commit(
                self.manifest,
                sha,
                verified=False,
                reason="unsigned",
            )

    client = UnsignedClient(
        manifest,
        contents,
    )

    client.target_head = (
        client.resulting_sha
    )

    with pytest.raises(
        hardened.SignedAuthoringHardeningError,
        match="signature is not verified",
    ):
        hardened.verify_published_commit(
            client=client,  # type: ignore[arg-type]
            manifest=manifest,
            resulting_sha=(
                client.resulting_sha
            ),
        )


def test_ref_lookup_maps_only_404_to_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GitHubActionsClient(
        app_id=1,
        installation_id=1,
        private_key="synthetic",
        repository="example/project",
    )

    def missing(
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del method, path, body

        raise GitHubActionsError(
            "not found",
            status_code=404,
        )

    monkeypatch.setattr(
        client,
        "_api",
        missing,
    )

    assert (
        client.get_ref_or_none(
            "missing"
        )
        is None
    )

    def forbidden(
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del method, path, body

        raise GitHubActionsError(
            "forbidden",
            status_code=403,
        )

    monkeypatch.setattr(
        client,
        "_api",
        forbidden,
    )

    with pytest.raises(
        GitHubActionsError,
    ) as error:
        client.get_ref_or_none(
            "forbidden"
        )

    assert (
        error.value.status_code
        == 403
    )


def test_graphql_commit_binds_expected_head_and_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GitHubActionsClient(
        app_id=1,
        installation_id=1,
        private_key="synthetic",
        repository="example/project",
    )

    captured: dict[str, Any] = {}

    operation_id = (
        "case-testy-author-synthetic"
    )

    def graphql(
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        captured["query"] = query
        captured["variables"] = variables

        return {
            "createCommitOnBranch": {
                "clientMutationId": (
                    operation_id
                ),
                "commit": {
                    "oid": "b" * 40,
                    "url": (
                        "https://example.invalid/"
                        "commit/"
                        + "b" * 40
                    ),
                },
                "ref": {
                    "name": (
                        "refs/heads/"
                        "case-testy/example"
                    ),
                    "target": {
                        "oid": "b" * 40,
                    },
                },
            }
        }

    monkeypatch.setattr(
        client,
        "_graphql",
        graphql,
    )

    result = (
        client.create_commit_on_branch(
            branch="case-testy/example",
            expected_head_oid="a" * 40,
            message_headline="synthetic",
            additions={
                "a.txt": "hello",
            },
            operation_id=operation_id,
        )
    )

    assert (
        result.commit_oid
        == "b" * 40
    )

    assert (
        result.ref_oid
        == result.commit_oid
    )

    assert (
        result.client_mutation_id
        == operation_id
    )

    input_data = (
        captured["variables"]["input"]
    )

    assert (
        input_data["expectedHeadOid"]
        == "a" * 40
    )

    assert (
        input_data["clientMutationId"]
        == operation_id
    )

    addition = (
        input_data["fileChanges"]
        ["additions"][0]
    )

    assert (
        addition["path"]
        == "a.txt"
    )

    assert (
        base64.b64decode(
            addition["contents"]
        ).decode("utf-8")
        == "hello"
    )


def test_canonical_workflow_uses_hardened_split_path() -> None:
    text = Path(
        ".github/workflows/"
        "case-testy-signed-authoring.yml"
    ).read_text(
        encoding="utf-8"
    )

    marker = (
        "- name: Publish immutable "
        "validated bytes"
    )

    assert marker in text

    prepare, publish = text.split(
        marker,
        1,
    )

    assert (
        "factory.quality."
        "case_signed_authoring_hardened"
        in prepare
    )

    assert (
        " prepare "
        in prepare.replace(
            "\n",
            " ",
        )
    )

    assert (
        "LUKART_ROS_FACTORY_PRIVATE_KEY"
        not in prepare
    )

    assert (
        "LUKART_ROS_FACTORY_PRIVATE_KEY"
        in publish
    )

    assert (
        " publish "
        in publish.replace(
            "\n",
            " ",
        )
    )

    assert (
        "force-push"
        not in text.lower()
    )


def test_canonical_standard_contains_privileged_authoring_invariant() -> None:
    text = Path(
        "docs/WORKING_PRINCIPLES.md"
    ).read_text(
        encoding="utf-8"
    )

    required = (
        "validated bytes = published bytes",
        "atomic publication",
        "compare-and-swap",
        "secret-free validation",
        "ambiguous write → reconcile",
        "no blind cleanup",
        "post-write verification",
        "no unsigned/unsafe fallback",
    )

    for rule in required:
        assert rule in text


def test_execution_profile_points_to_canonical_authority() -> None:
    text = Path(
        "docs/execution_profiles/"
        "SIGNED_AUTHORING_HARDENING.md"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "docs/WORKING_PRINCIPLES.md"
        in text
    )

    assert (
        "non-authoritative"
        in text.lower()
    )

def test_legacy_authoring_module_is_pure_single_writer_boundary() -> None:
    import ast

    legacy_path = Path(
        "factory/quality/case_signed_authoring.py"
    )
    hardened_path = Path(
        "factory/quality/case_signed_authoring_hardened.py"
    )

    legacy_source = legacy_path.read_text(
        encoding="utf-8"
    )

    forbidden_fragments = (
        "GitHubActionsClient",
        "GitHubActionsError",
        "from_environment(",
        "._api(",
        "put_file(",
        "delete_branch_best_effort(",
        "create_pull_request(",
        "verify_commit(",
        "harden_manual_smoke_inventory(",
        "subprocess",
        "argparse",
        "base64",
        "urllib.parse",
        "os.environ",
        'if __name__ == "__main__"',
    )

    for fragment in forbidden_fragments:
        assert fragment not in legacy_source, fragment

    legacy_tree = ast.parse(legacy_source)

    actual_functions = {
        node.name
        for node in legacy_tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    assert actual_functions == {
        "require",
        "replace_once",
        "render_regression_suite_update",
        "render_test_file",
    }

    actual_classes = {
        node.name
        for node in legacy_tree.body
        if isinstance(node, ast.ClassDef)
    }

    assert actual_classes == {
        "SignedAuthoringError",
    }

    runtime_imports = [
        node
        for node in legacy_tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
        )
    ]

    assert runtime_imports == []

    hardened_tree = ast.parse(
        hardened_path.read_text(
            encoding="utf-8"
        )
    )

    imported_from_legacy = {
        alias.name
        for node in hardened_tree.body
        if isinstance(node, ast.ImportFrom)
        and (
            node.module
            == "factory.quality.case_signed_authoring"
        )
        for alias in node.names
    }

    assert imported_from_legacy == {
        "ALLOWED_PATHS",
        "MAIN_BRANCH",
        "OPERATION",
        "TARGET_BRANCH",
        "render_regression_suite_update",
        "render_test_file",
    }
