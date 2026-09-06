"""Shared P3 integrity contracts.

P3 treats canonical bytes, content digests and explicit trust boundaries as
public contracts.  These helpers deliberately contain no Product reasoning
logic; they only protect transport, persistence and orchestration boundaries.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class P3ContractError(ValueError):
    """Fail-closed contract violation at a P3 boundary."""


class TrustLevel(StrEnum):
    UNTRUSTED = "UNTRUSTED"
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    TRUSTED = "TRUSTED"


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Exact execution identity required for reproducible replay."""

    code_sha: str
    schema_version: str
    config_digest: str
    corpus_digest: str
    provider_identities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.code_sha,
            self.schema_version,
            self.config_digest,
            self.corpus_digest,
        )
        if any(not value.strip() for value in values):
            raise P3ContractError("runtime identity fields cannot be blank")
        normalized = tuple(sorted({item.strip() for item in self.provider_identities}))
        if any(not item for item in normalized):
            raise P3ContractError("provider identities cannot be blank")
        object.__setattr__(self, "provider_identities", normalized)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "code_sha": self.code_sha,
            "schema_version": self.schema_version,
            "config_digest": self.config_digest,
            "corpus_digest": self.corpus_digest,
            "provider_identities": list(self.provider_identities),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, set | frozenset):
        normalized = [_normalize(item) for item in value]
        return sorted(normalized, key=lambda item: canonical_json(item))
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "canonical_dict"):
        canonical = value.canonical_dict()
        if not isinstance(canonical, Mapping):
            raise P3ContractError("canonical_dict() must return a mapping")
        return _normalize(canonical)
    raise P3ContractError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return deterministic UTF-8 JSON representation for supported values."""

    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_digest(value: object, expected_digest: str) -> None:
    actual = content_digest(value)
    if not expected_digest or actual != expected_digest:
        raise P3ContractError("content digest mismatch")


def require_unique_nonblank(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in values)
    if any(not item for item in normalized):
        raise P3ContractError(f"{field_name} cannot contain blank values")
    if len(set(normalized)) != len(normalized):
        raise P3ContractError(f"{field_name} cannot contain duplicates")
    return normalized
