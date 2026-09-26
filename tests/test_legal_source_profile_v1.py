from __future__ import annotations

import pytest

from core.legal_authority import (
    AuthorityCapability,
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    PrivacyClass,
    SourceAccessMode,
    SourceClass,
    TemporalCoverage,
)


def _profile(**overrides: object) -> LegalSourceProfile:
    values: dict[str, object] = {
        "source_id": "PL.TEST.OFFICIAL",
        "jurisdiction": "PL",
        "institution": "Synthetic Official Institution",
        "source_classes": (SourceClass.PRIMARY_PUBLICATION,),
        "authority_capabilities": (
            AuthorityCapability.PUBLICATION_IDENTITY,
            AuthorityCapability.NORM_TEXT,
            AuthorityCapability.TEMPORAL_STATUS,
        ),
        "privacy_class": PrivacyClass.PUBLIC,
        "access_mode": SourceAccessMode.WEB,
        "canonical_base_uri": "https://official.example.test/legal",
        "allowed_hosts": ("official.example.test",),
        "temporal_coverage": TemporalCoverage.EXACT,
        "fallback_policy": FallbackPolicy.NONE,
    }
    values.update(overrides)
    return LegalSourceProfile(**values)  # type: ignore[arg-type]


def test_primary_official_exact_source_has_capability_specific_authority() -> None:
    profile = _profile()

    assert profile.can_establish(AuthorityCapability.PUBLICATION_IDENTITY)
    assert profile.can_establish(AuthorityCapability.NORM_TEXT)
    assert not profile.can_establish(AuthorityCapability.JUDGMENT_FULL_TEXT)
    assert profile.can_establish_temporal_applicability
    assert profile.permits_host("OFFICIAL.EXAMPLE.TEST")


def test_metadata_source_is_authoritative_only_for_declared_capability() -> None:
    profile = _profile(
        source_id="CO.TEST.METADATA",
        jurisdiction="CO",
        source_classes=(SourceClass.OFFICIAL_OPEN_DATA,),
        authority_capabilities=(
            AuthorityCapability.CITATION_METADATA,
            AuthorityCapability.DISCOVERY,
        ),
        temporal_coverage=TemporalCoverage.PARTIAL,
    )

    assert profile.is_official
    assert profile.can_establish(AuthorityCapability.CITATION_METADATA)
    assert not profile.can_establish(AuthorityCapability.JUDGMENT_FULL_TEXT)
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
        {"source_classes": ()},
        {"authority_capabilities": ()},
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


def test_profile_supports_multiple_source_classes_and_private_data_axis() -> None:
    profile = _profile(
        source_id="CO.TEST.OPERATIONAL.PRIVATE",
        source_classes=(SourceClass.OFFICIAL_OPERATIONAL,),
        authority_capabilities=(AuthorityCapability.OPERATIONAL_STATE,),
        privacy_class=PrivacyClass.PRIVATE_CASE_DATA,
        temporal_coverage=TemporalCoverage.PARTIAL,
    )

    assert profile.source_classes == (SourceClass.OFFICIAL_OPERATIONAL,)
    assert profile.privacy_class is PrivacyClass.PRIVATE_CASE_DATA
    assert profile.can_establish(AuthorityCapability.OPERATIONAL_STATE)
    assert not profile.can_establish(AuthorityCapability.NORM_TEXT)


def test_profile_rejects_mixed_derived_and_official_source_classes() -> None:
    with pytest.raises(LegalAuthorityContractError):
        _profile(
            source_classes=(
                SourceClass.DERIVED_OPEN_SOURCE,
                SourceClass.OFFICIAL_OPEN_DATA,
            ),
            authority_capabilities=(AuthorityCapability.DISCOVERY,),
        )
