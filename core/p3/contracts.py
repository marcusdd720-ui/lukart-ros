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


def require_hex_digest(
    value: str,
    *,
    field_name: str,
    lengths: tuple[int, ...] = (64,),
) -> str:
    normalized = value.strip().lower()
    if len(normalized) not in lengths:
        allowed = "/".join(str(length) for length in lengths)
        raise P3ContractError(f"{field_name} must be a {allowed}-character hex digest")
    if any(character not in "0123456789abcdef" for character in normalized):
        raise P3ContractError(f"{field_name} must contain hexadecimal characters only")
    return normalized


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Exact execution identity required for reproducible replay."""

    code_sha: str
    schema_version: str
    config_digest: str
    corpus_digest: str
    provider_identities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        schema_version = self.schema_version.strip()
        if not schema_version:
            raise P3ContractError("schema_version cannot be blank")
        code_sha = require_hex_digest(
            self.code_sha,
            field_name="code_sha",
            lengths=(40, 64),
        )
        config_digest = require_hex_digest(
            self.config_digest,
            field_name="config_digest",
        )
        corpus_digest = require_hex_digest(
            self.corpus_digest,
            field_name="corpus_digest",
        )
        normalized = tuple(sorted({item.strip() for item in self.provider_identities}))
        if any(not item for item in normalized):
            raise P3ContractError("provider identities cannot be blank")
        object.__setattr__(self, "code_sha", code_sha)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "config_digest", config_digest)
        object.__setattr__(self, "corpus_digest", corpus_digest)
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
        items = sorted(value.items(), key=lambda item: str(item[0]))
        return {str(key): _normalize(item) for key, item in items}
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
    expected = require_hex_digest(expected_digest, field_name="expected_digest")
    actual = content_digest(value)
    if actual != expected:
        raise P3ContractError("content digest mismatch")


def require_unique_nonblank(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in values)
    if any(not item for item in normalized):
        raise P3ContractError(f"{field_name} cannot contain blank values")
    if len(set(normalized)) != len(normalized):
        raise P3ContractError(f"{field_name} cannot contain duplicates")
    return normalized
