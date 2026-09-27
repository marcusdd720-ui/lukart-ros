"""Deterministic execution-environment fingerprint for Night Shift evidence."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class FileDigest:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    python_implementation: str
    python_version: str
    system: str
    release: str
    machine: str
    git_version: str
    policy_version: str
    lockfiles: tuple[FileDigest, ...]
    iana_timezone_probe: str
    iana_timezone_available: bool

    def canonical_dict(self) -> dict[str, object]:
        return {
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "system": self.system,
            "release": self.release,
            "machine": self.machine,
            "git_version": self.git_version,
            "policy_version": self.policy_version,
            "lockfiles": [
                {"path": item.path, "sha256": item.sha256} for item in self.lockfiles
            ],
            "iana_timezone_probe": self.iana_timezone_probe,
            "iana_timezone_available": self.iana_timezone_available,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_version() -> str:
    completed = subprocess.run(
        ["git", "--version"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise NightShiftContractError("git version probe failed")
    value = completed.stdout.strip()
    if not value:
        raise NightShiftContractError("git version probe returned blank output")
    return value


def _zoneinfo_available(key: str) -> bool:
    try:
        ZoneInfo(key)
    except ZoneInfoNotFoundError:
        return False
    return True
def collect_environment_fingerprint(
    *,
    repository: str | Path,
    policy_version: str,
    lockfile_names: tuple[str, ...] = ("uv.lock", "pylock.toml"),
    timezone_probe: str = "Europe/Warsaw",
) -> EnvironmentFingerprint:
    repo = Path(repository).resolve()
    if not repo.is_dir():
        raise NightShiftContractError("repository path does not exist")

    policy = policy_version.strip()
    probe = timezone_probe.strip()
    if not policy:
        raise NightShiftContractError("policy_version is required")
    if not probe:
        raise NightShiftContractError("timezone_probe is required")

    lockfiles: list[FileDigest] = []
    for name in sorted(set(lockfile_names)):
        normalized = name.strip()
        if not normalized:
            raise NightShiftContractError("lockfile_names cannot contain blanks")
        candidate = (repo / normalized).resolve()
        try:
            candidate.relative_to(repo)
        except ValueError as exc:
            raise NightShiftContractError("lockfile path escaped repository") from exc
        if candidate.is_file():
            lockfiles.append(
                FileDigest(
                    path=candidate.relative_to(repo).as_posix(),
                    sha256=_file_sha256(candidate),
                )
            )

    if not lockfiles:
        raise NightShiftContractError("no declared dependency lockfile found")

    return EnvironmentFingerprint(
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        git_version=_git_version(),
        policy_version=policy,
        lockfiles=tuple(lockfiles),
        iana_timezone_probe=probe,
        iana_timezone_available=_zoneinfo_available(probe),
    )
