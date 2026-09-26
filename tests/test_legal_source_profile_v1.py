from __future__ import annotations

import pytest

from core.legal_authority import (
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    SourceAccessMode,
    SourceAuthorityClass,
    TemporalCoverage,
)


def _profile(**overrides: object) -> LegalSourceProfile:
    values: dict[str, object] = {
        "source_id": "PL.TEST.OFFICIAL",
        "jurisdiction": "PL",
        "institution": "Synthetic Official Institution",
        "authority_class": SourceAuthorityClass.PRIMARY_OFFICIAL,
        "access_mode": SourceAccessMode.WEB,
        "canonical_base_uri": "https://official.example.test/legal",
        "allowed_hosts": ("official.example.test",),
        "temporal_coverage": TemporalCoverage.EXACT,
        "fallback_policy": FallbackPolicy.NONE,
    }
    values.update(overrides)
    return LegalSourceProfile(**values)  # type: ignore[arg-type]


def test_primary_official_exact_source_can_establish_authority_and_time() -> None:
    profile = _profile()

    assert profile.can_establish_authority
    assert profile.can_establish_temporal_applicability
    assert profile.permits_host("OFFICIAL.EXAMPLE.TEST")


def test_discovery_source_cannot_establish_authority() -> None:
    profile = _profile(
        source_id="CO.TEST.DISCOVERY",
        jurisdiction="CO",
        authority_class=SourceAuthorityClass.OFFICIAL_DISCOVERY,
        temporal_coverage=TemporalCoverage.PARTIAL,
    )

    assert not profile.can_establish_authority
    assert not profile.can_establish_temporal_applicability


@pytest.mark.parametrize(
    "overrides",
    [
        {"canonical_base_uri": "http://official.example.test/legal"},
        {
            "canonical_base_uri": "https://other.example.test/legal",
            "allowed_hosts": ("official.example.test",),
        },
        {"allowed_hosts": ()},
        {
            "fallback_policy": FallbackPolicy.NONE,
            "fallback_source_ids": ("PL.OTHER",),
        },
        {
            "fallback_policy": FallbackPolicy.OFFICIAL_ONLY,
            "fallback_source_ids": (),
        },
        {
            "fallback_policy": FallbackPolicy.OFFICIAL_ONLY,
            "fallback_source_ids": ("PL.TEST.OFFICIAL",),
        },
    ],
)
def test_invalid_profile_boundaries_fail_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(LegalAuthorityContractError):
        _profile(**overrides)


def test_explicit_official_fallback_chain_is_accepted() -> None:
    profile = _profile(
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("PL.TEST.OFFICIAL.REPUBLICATION",),
    )

    assert profile.fallback_source_ids == ("PL.TEST.OFFICIAL.REPUBLICATION",)
