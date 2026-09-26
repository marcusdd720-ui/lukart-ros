"""Legal Authority Fabric public contracts."""

from .contracts import (
    LEGAL_SOURCE_PROFILE_SCHEMA_V1,
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    SourceAccessMode,
    SourceAuthorityClass,
    TemporalCoverage,
)
from .registry import LegalSourceRegistry

__all__ = [
    "LEGAL_SOURCE_PROFILE_SCHEMA_V1",
    "FallbackPolicy",
    "LegalAuthorityContractError",
    "LegalSourceProfile",
    "LegalSourceRegistry",
    "SourceAccessMode",
    "SourceAuthorityClass",
    "TemporalCoverage",
]
