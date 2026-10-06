"""Legal Authority Fabric public contracts."""

from .contracts import (
    LEGAL_SOURCE_PROFILE_SCHEMA_V1,
    AuthorityCapability,
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    PrivacyClass,
    SourceAccessMode,
    SourceClass,
    TemporalCoverage,
)
from .registry import LegalSourceRegistry

__all__ = [
    "LEGAL_SOURCE_PROFILE_SCHEMA_V1",
    "AuthorityCapability",
    "FallbackPolicy",
    "LegalAuthorityContractError",
    "LegalSourceProfile",
    "LegalSourceRegistry",
    "PrivacyClass",
    "SourceAccessMode",
    "SourceClass",
    "TemporalCoverage",
]
