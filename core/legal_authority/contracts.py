"""Typed contracts for the LUKART Legal Authority Fabric.

These contracts describe legal-source capabilities and trust boundaries.
They do not fetch content and do not promote discovered material to authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

LEGAL_SOURCE_PROFILE_SCHEMA_V1 = "lukart.legal-authority.source-profile.v1"


class LegalAuthorityContractError(ValueError):
    """Fail-closed legal-authority contract violation."""


class SourceAuthorityClass(StrEnum):
    PRIMARY_OFFICIAL = "PRIMARY_OFFICIAL"
    OFFICIAL_REPUBLICATION = "OFFICIAL_REPUBLICATION"
    OFFICIAL_DISCOVERY = "OFFICIAL_DISCOVERY"
    NON_AUTHORITATIVE_DISCOVERY = "NON_AUTHORITATIVE_DISCOVERY"


class SourceAccessMode(StrEnum):
    WEB = "WEB"
    API = "API"
    WEB_AND_API = "WEB_AND_API"


class TemporalCoverage(StrEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"

class FallbackPolicy(StrEnum):
    NONE = "NONE"
    OFFICIAL_ONLY = "OFFICIAL_ONLY"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


def _nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise LegalAuthorityContractError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _canonical_host(value: str) -> str:
    host = _nonblank(value, field_name="allowed_host").lower()
    if "://" in host or "/" in host:
        raise LegalAuthorityContractError("allowed_host must be a hostname only")
    return host


@dataclass(frozen=True, slots=True)
class LegalSourceProfile:
    source_id: str
    jurisdiction: str
    institution: str
    authority_class: SourceAuthorityClass
    access_mode: SourceAccessMode
    canonical_base_uri: str
    allowed_hosts: tuple[str, ...]
    temporal_coverage: TemporalCoverage
    fallback_policy: FallbackPolicy
    fallback_source_ids: tuple[str, ...] = ()
    schema: str = LEGAL_SOURCE_PROFILE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEGAL_SOURCE_PROFILE_SCHEMA_V1:
            raise LegalAuthorityContractError("unsupported legal source profile schema")
        for field_name in ("source_id", "jurisdiction", "institution"):
            object.__setattr__(
                self,
                field_name,
                _nonblank(getattr(self, field_name), field_name=field_name),
            )

        parsed = urlparse(self.canonical_base_uri)
        if parsed.scheme != "https" or not parsed.hostname:
            raise LegalAuthorityContractError(
                "canonical_base_uri must be an absolute https URI"
            )

        hosts = tuple(_canonical_host(item) for item in self.allowed_hosts)
        if not hosts or len(hosts) != len(set(hosts)):
            raise LegalAuthorityContractError(
                "allowed_hosts must be non-empty and contain no duplicates"
            )
        if parsed.hostname.lower() not in hosts:
            raise LegalAuthorityContractError(
                "canonical_base_uri host must be present in allowed_hosts"
            )
        object.__setattr__(self, "allowed_hosts", hosts)

        fallbacks = tuple(
            _nonblank(item, field_name="fallback_source_id")
            for item in self.fallback_source_ids
        )
        if len(fallbacks) != len(set(fallbacks)):
            raise LegalAuthorityContractError(
                "fallback_source_ids cannot contain duplicates"
            )
        if self.source_id in fallbacks:
            raise LegalAuthorityContractError("source cannot fallback to itself")
        object.__setattr__(self, "fallback_source_ids", fallbacks)

        if self.fallback_policy is FallbackPolicy.NONE and fallbacks:
            raise LegalAuthorityContractError(
                "fallback_source_ids require a non-NONE fallback policy"
            )
        if self.fallback_policy is not FallbackPolicy.NONE and not fallbacks:
            raise LegalAuthorityContractError(
                "non-NONE fallback policy requires fallback_source_ids"
            )

    @property
    def can_establish_authority(self) -> bool:
        return self.authority_class in {
            SourceAuthorityClass.PRIMARY_OFFICIAL,
            SourceAuthorityClass.OFFICIAL_REPUBLICATION,
        }

    @property
    def can_establish_temporal_applicability(self) -> bool:
        return self.temporal_coverage is TemporalCoverage.EXACT

    def permits_host(self, host: str) -> bool:
        return _canonical_host(host) in self.allowed_hosts

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_id": self.source_id,
            "jurisdiction": self.jurisdiction,
            "institution": self.institution,
            "authority_class": self.authority_class.value,
            "access_mode": self.access_mode.value,
            "canonical_base_uri": self.canonical_base_uri,
            "allowed_hosts": list(self.allowed_hosts),
            "temporal_coverage": self.temporal_coverage.value,
            "fallback_policy": self.fallback_policy.value,
            "fallback_source_ids": list(self.fallback_source_ids),
        }
