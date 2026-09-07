"""PEP 517 backend guard for LUKART ROS immutable historical releases."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent


def _setuptools_backend() -> Any:
    """Load setuptools only inside the isolated PEP 517 build environment."""

    from setuptools import build_meta

    return build_meta


def _project_state() -> tuple[str, str, str]:
    with (_ROOT / "pyproject.toml").open("rb") as stream:
        config = tomllib.load(stream)
    project_version = str(config["project"]["version"]).strip()
    enterprise = config["tool"]["lukart"]["enterprise"]
    baseline_version = str(enterprise["immutable_baseline_version"]).strip()
    baseline_commit = str(enterprise["immutable_baseline_commit"]).strip().lower()
    return project_version, baseline_version, baseline_commit


def _source_sha() -> str:
    explicit = os.environ.get("LUKART_SOURCE_SHA", "").strip().lower()
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("cannot verify source SHA for immutable baseline build") from exc
    return result.stdout.strip().lower()


def _enforce_immutable_baseline() -> None:
    project_version, baseline_version, baseline_commit = _project_state()
    if project_version != baseline_version:
        return
    actual = _source_sha()
    if actual != baseline_commit:
        raise RuntimeError(
            "immutable baseline version may only be built from its exact historical commit: "
            f"expected {baseline_commit}, got {actual or 'UNKNOWN'}"
        )


def build_wheel(
    wheel_directory: str,
    config_settings: Any = None,
    metadata_directory: str | None = None,
) -> str:
    _enforce_immutable_baseline()
    return _setuptools_backend().build_wheel(
        wheel_directory, config_settings, metadata_directory
    )


def build_sdist(sdist_directory: str, config_settings: Any = None) -> str:
    _enforce_immutable_baseline()
    return _setuptools_backend().build_sdist(sdist_directory, config_settings)


def build_editable(
    wheel_directory: str,
    config_settings: Any = None,
    metadata_directory: str | None = None,
) -> str:
    _enforce_immutable_baseline()
    return _setuptools_backend().build_editable(
        wheel_directory, config_settings, metadata_directory
    )


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: Any = None
) -> str:
    _enforce_immutable_baseline()
    return _setuptools_backend().prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: Any = None
) -> str:
    _enforce_immutable_baseline()
    return _setuptools_backend().prepare_metadata_for_build_editable(
        metadata_directory, config_settings
    )


def get_requires_for_build_wheel(config_settings: Any = None) -> list[str]:
    _enforce_immutable_baseline()
    return _setuptools_backend().get_requires_for_build_wheel(config_settings)


def get_requires_for_build_sdist(config_settings: Any = None) -> list[str]:
    _enforce_immutable_baseline()
    return _setuptools_backend().get_requires_for_build_sdist(config_settings)


def get_requires_for_build_editable(config_settings: Any = None) -> list[str]:
    _enforce_immutable_baseline()
    return _setuptools_backend().get_requires_for_build_editable(config_settings)
