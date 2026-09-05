"""Explicit certification profile for independent and solo-maintainer release tracks."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from validation.human_review_provenance import EXPECTED_REPOSITORY

PROFILE_PATH = Path("factory/certification_profile.json")
EXPECTED_MAINTAINER_ID = EXPECTED_REPOSITORY.split("/", 1)[0]


class CertificationMode(StrEnum):
    INDEPENDENT = "independent"
    SOLO_MAINTAINER = "solo_maintainer"


class CertificationProfileError(ValueError):
    """Raised when the repository certification profile is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class CertificationProfile:
    schema_version: str
    mode: CertificationMode
    maintainer_id: str
    authorized_by: str
    independent_external_review: str
    authorization_reason: str


def independent_default_profile() -> CertificationProfile:
    """Return the fail-closed legacy/default profile when no explicit profile exists."""

    return CertificationProfile(
        schema_version="1.0",
        mode=CertificationMode.INDEPENDENT,
        maintainer_id=EXPECTED_MAINTAINER_ID,
        authorized_by=EXPECTED_MAINTAINER_ID,
        independent_external_review="REQUIRED",
        authorization_reason="Default fail-closed independent certification profile.",
    )


def _required_text(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise CertificationProfileError(
            f"certification profile field {name} must be non-empty text"
        )
    return value.strip()


def load_certification_profile(
    root: Path,
    *,
    required: bool = False,
) -> CertificationProfile:
    """Load and validate the repository certification profile.

    Missing profile means the historical strict independent mode unless ``required`` is true.
    Solo mode is never inferred: it must be explicitly committed and internally consistent.
    """

    path = root / PROFILE_PATH
    if not path.is_file():
        if required:
            raise CertificationProfileError(
                f"explicit certification profile is required for solo mode: {PROFILE_PATH}"
            )
        return independent_default_profile()

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CertificationProfileError("certification profile must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise CertificationProfileError("certification profile must be a JSON object")

    schema_version = _required_text(value, "schema_version")
    if schema_version != "1.0":
        raise CertificationProfileError("certification profile schema_version must be 1.0")

    raw_mode = _required_text(value, "mode")
    try:
        mode = CertificationMode(raw_mode)
    except ValueError as exc:
        raise CertificationProfileError(f"unsupported certification mode: {raw_mode}") from exc

    maintainer_id = _required_text(value, "maintainer_id")
    authorized_by = _required_text(value, "authorized_by")
    independent_external_review = _required_text(value, "independent_external_review")
    authorization_reason = _required_text(value, "authorization_reason")

    if maintainer_id != EXPECTED_MAINTAINER_ID or authorized_by != EXPECTED_MAINTAINER_ID:
        raise CertificationProfileError(
            "certification profile maintainer/authorizer must be the repository owner"
        )

    expected_external = (
        "NOT_PERFORMED"
        if mode is CertificationMode.SOLO_MAINTAINER
        else "REQUIRED"
    )
    if independent_external_review != expected_external:
        raise CertificationProfileError(
            "independent_external_review is inconsistent with certification mode"
        )

    return CertificationProfile(
        schema_version=schema_version,
        mode=mode,
        maintainer_id=maintainer_id,
        authorized_by=authorized_by,
        independent_external_review=independent_external_review,
        authorization_reason=authorization_reason,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    profile = load_certification_profile(args.root)
    print(profile.mode.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
