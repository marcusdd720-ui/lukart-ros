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


class SourceClass(StrEnum):
    PRIMARY_PUBLICATION = "PRIMARY_PUBLICATION"
    OFFICIAL_CONSOLIDATED = "OFFICIAL_CONSOLIDATED"
    OFFICIAL_JURISPRUDENCE = "OFFICIAL_JURISPRUDENCE"
    OFFICIAL_OPEN_DATA = "OFFICIAL_OPEN_DATA"
    OFFICIAL_OPERATIONAL = "OFFICIAL_OPERATIONAL"
    DERIVED_OPEN_SOURCE = "DERIVED_OPEN_SOURCE"


class PrivacyClass(StrEnum):
    PUBLIC = "PUBLIC"
    CASE_SENSITIVE = "CASE_SENSITIVE"
    PRIVATE_CASE_DATA = "PRIVATE_CASE_DATA"


class AuthorityCapability(StrEnum):
    PUBLICATION_IDENTITY = "PUBLICATION_IDENTITY"
    NORM_TEXT = "NORM_TEXT"
    TEMPORAL_STATUS = "TEMPORAL_STATUS"
    JUDGMENT_FULL_TEXT = "JUDGMENT_FULL_TEXT"
    CITATION_METADATA = "CITATION_METADATA"
    OPERATIONAL_STATE = "OPERATIONAL_STATE"
    DISCOVERY = "DISCOVERY"


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
    source_classes: tuple[SourceClass, ...]
    authority_capabilities: tuple[AuthorityCapability, ...]
    privacy_class: PrivacyClass
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

        source_classes = tuple(self.source_classes)
        if not source_classes or len(source_classes) != len(set(source_classes)):
            raise LegalAuthorityContractError(
                "source_classes must be non-empty and contain no duplicates"
            )
        if (
            SourceClass.DERIVED_OPEN_SOURCE in source_classes
            and len(source_classes) != 1
        ):
            raise LegalAuthorityContractError(
                "DERIVED_OPEN_SOURCE cannot be mixed with official source classes"
            )
        object.__setattr__(self, "source_classes", source_classes)

        capabilities = tuple(self.authority_capabilities)
        if not capabilities or len(capabilities) != len(set(capabilities)):
            raise LegalAuthorityContractError(
                "authority_capabilities must be non-empty and contain no duplicates"
            )
        object.__setattr__(self, "authority_capabilities", capabilities)

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
    def is_official(self) -> bool:
        return any(
            source_class is not SourceClass.DERIVED_OPEN_SOURCE
            for source_class in self.source_classes
        )

    def can_establish(self, capability: AuthorityCapability) -> bool:
        return capability in self.authority_capabilities

    @property
    def can_establish_temporal_applicability(self) -> bool:
        return (
            self.temporal_coverage is TemporalCoverage.EXACT
            and self.can_establish(AuthorityCapability.TEMPORAL_STATUS)
        )

    def permits_host(self, host: str) -> bool:
        return _canonical_host(host) in self.allowed_hosts

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_id": self.source_id,
            "jurisdiction": self.jurisdiction,
            "institution": self.institution,
            "source_classes": [item.value for item in self.source_classes],
            "authority_capabilities": [
                item.value for item in self.authority_capabilities
            ],
            "privacy_class": self.privacy_class.value,
            "access_mode": self.access_mode.value,
            "canonical_base_uri": self.canonical_base_uri,
            "allowed_hosts": list(self.allowed_hosts),
            "temporal_coverage": self.temporal_coverage.value,
            "fallback_policy": self.fallback_policy.value,
            "fallback_source_ids": list(self.fallback_source_ids),
        }
