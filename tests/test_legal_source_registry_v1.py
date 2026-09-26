from __future__ import annotations

import pytest

from core.legal_authority import (
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    LegalSourceRegistry,
    SourceAccessMode,
    SourceAuthorityClass,
    TemporalCoverage,
)


def _profile(
    source_id: str,
    *,
    authority_class: SourceAuthorityClass = SourceAuthorityClass.PRIMARY_OFFICIAL,
    fallback_policy: FallbackPolicy = FallbackPolicy.NONE,
    fallback_source_ids: tuple[str, ...] = (),
) -> LegalSourceProfile:
    host = source_id.lower().replace("_", "-") + ".example.test"
    return LegalSourceProfile(
        source_id=source_id,
        jurisdiction="TEST",
        institution=f"Institution {source_id}",
        authority_class=authority_class,
        access_mode=SourceAccessMode.WEB,
        canonical_base_uri=f"https://{host}/",
        allowed_hosts=(host,),
        temporal_coverage=TemporalCoverage.EXACT,
        fallback_policy=fallback_policy,
        fallback_source_ids=fallback_source_ids,
    )


def test_registry_lookup_and_official_fallback_chain() -> None:
    backup = _profile("TEST.BACKUP")
    primary = _profile(
        "TEST.PRIMARY",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.BACKUP",),
    )
    registry = LegalSourceRegistry((primary, backup))

    assert registry.source_ids() == ("TEST.BACKUP", "TEST.PRIMARY")
    assert registry.get("TEST.PRIMARY") is primary
    assert registry.fallback_chain("TEST.PRIMARY") == (backup,)


def test_registry_rejects_unknown_source() -> None:
    registry = LegalSourceRegistry((_profile("TEST.ONLY"),))

    with pytest.raises(LegalAuthorityContractError):
        registry.get("TEST.MISSING")


def test_registry_rejects_duplicate_source_id() -> None:
    with pytest.raises(LegalAuthorityContractError):
        LegalSourceRegistry((_profile("TEST.DUP"), _profile("TEST.DUP")))


def test_registry_rejects_unknown_fallback_target() -> None:
    primary = _profile(
        "TEST.PRIMARY",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.MISSING",),
    )

    with pytest.raises(LegalAuthorityContractError):
        LegalSourceRegistry((primary,))


def test_registry_rejects_non_authority_official_fallback() -> None:
    discovery = _profile(
        "TEST.DISCOVERY",
        authority_class=SourceAuthorityClass.OFFICIAL_DISCOVERY,
    )
    primary = _profile(
        "TEST.PRIMARY",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.DISCOVERY",),
    )

    with pytest.raises(LegalAuthorityContractError):
        LegalSourceRegistry((primary, discovery))


def test_registry_rejects_fallback_cycle() -> None:
    left = _profile(
        "TEST.LEFT",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.RIGHT",),
    )
    right = _profile(
        "TEST.RIGHT",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.LEFT",),
    )

    with pytest.raises(LegalAuthorityContractError):
        LegalSourceRegistry((left, right))
