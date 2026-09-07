"""Canonical fail-closed future-release intent contract.

`[project].version` is the only current-version source of truth. Historical
baseline identity remains separate and immutable. This module deliberately
contains no release mutation logic.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_STABLE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
_HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ReleaseContractError(RuntimeError):
    """Raised when release intent cannot be trusted."""


@dataclass(frozen=True, slots=True)
class ReleaseIntent:
    project_version: str
    release_enabled: bool
    immutable_baseline_version: str
    immutable_baseline_commit: str
    immutable_releases_required: bool

    @property
    def tag(self) -> str:
        return f"v{self.project_version}" if self.release_enabled else ""

    def github_outputs(self) -> tuple[str, ...]:
        return (
            f"release={'true' if self.release_enabled else 'false'}",
            f"version={self.project_version}",
            f"tag={self.tag}",
            f"immutable_baseline={self.immutable_baseline_version}",
            f"immutable_baseline_commit={self.immutable_baseline_commit}",
            f"immutable_releases_required={'true' if self.immutable_releases_required else 'false'}",
        )


def resolve_release_intent(data: object) -> ReleaseIntent:
    if not isinstance(data, dict):
        raise ReleaseContractError("pyproject root must be a table")

    project = data.get("project")
    tool = data.get("tool")
    if not isinstance(project, dict) or not isinstance(tool, dict):
        raise ReleaseContractError("project/tool configuration is missing")
    lukart = tool.get("lukart")
    if not isinstance(lukart, dict):
        raise ReleaseContractError("tool.lukart configuration is missing")
    enterprise = lukart.get("enterprise")
    if not isinstance(enterprise, dict):
        raise ReleaseContractError("tool.lukart.enterprise configuration is missing")

    if "development_version" in enterprise:
        raise ReleaseContractError(
            "development_version is forbidden: [project].version is the current-version SSOT"
        )

    version = project.get("version")
    baseline_version = enterprise.get("immutable_baseline_version")
    baseline_commit = enterprise.get("immutable_baseline_commit")
    release_enabled = enterprise.get("release_enabled")
    immutable_required = enterprise.get("immutable_releases_required")

    if not isinstance(version, str) or not version.strip():
        raise ReleaseContractError("project.version must be a non-empty string")
    if not isinstance(baseline_version, str) or not _STABLE_VERSION.fullmatch(
        baseline_version.strip()
    ):
        raise ReleaseContractError("immutable baseline version must be stable X.Y.Z")
    if not isinstance(baseline_commit, str) or not _HEX_SHA.fullmatch(
        baseline_commit.strip().lower()
    ):
        raise ReleaseContractError("immutable baseline commit must be an exact 40-hex SHA")
    if not isinstance(release_enabled, bool):
        raise ReleaseContractError("release_enabled must be boolean")
    if immutable_required is not True:
        raise ReleaseContractError("future releases must require repository release immutability")

    version = version.strip()
    baseline_version = baseline_version.strip()
    baseline_commit = baseline_commit.strip().lower()

    if release_enabled:
        if not _STABLE_VERSION.fullmatch(version):
            raise ReleaseContractError("release-enabled project version must be stable X.Y.Z")
        if version == baseline_version:
            raise ReleaseContractError("immutable historical baseline cannot be released again")

    return ReleaseIntent(
        project_version=version,
        release_enabled=release_enabled,
        immutable_baseline_version=baseline_version,
        immutable_baseline_commit=baseline_commit,
        immutable_releases_required=True,
    )


def load_release_intent(path: Path) -> ReleaseIntent:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseContractError(f"cannot read canonical release configuration: {path}") from exc
    return resolve_release_intent(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve canonical future-release intent")
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    intent = load_release_intent(Path(args.pyproject))
    lines = intent.github_outputs()
    for line in lines:
        print(line)
    if args.github_output:
        output = Path(args.github_output)
        with output.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
