from __future__ import annotations

import pytest

from core.legal_authority import (
    AuthorityCapability,
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
    LegalSourceRegistry,
    PrivacyClass,
    SourceAccessMode,
    SourceClass,
    TemporalCoverage,
)


def _profile(
    source_id: str,
    *,
    source_classes: tuple[SourceClass, ...] = (
        SourceClass.PRIMARY_PUBLICATION,
    ),
    authority_capabilities: tuple[AuthorityCapability, ...] = (
        AuthorityCapability.PUBLICATION_IDENTITY,
    ),
    privacy_class: PrivacyClass = PrivacyClass.PUBLIC,
    fallback_policy: FallbackPolicy = FallbackPolicy.NONE,
    fallback_source_ids: tuple[str, ...] = (),
) -> LegalSourceProfile:
    host = source_id.lower().replace("_", "-") + ".example.test"
    return LegalSourceProfile(
        source_id=source_id,
        jurisdiction="TEST",
        institution=f"Institution {source_id}",
        source_classes=source_classes,
        authority_capabilities=authority_capabilities,
        privacy_class=privacy_class,
        access_mode=SourceAccessMode.WEB,
        canonical_base_uri=f"https://{host}/",
        allowed_hosts=(host,),
        temporal_coverage=TemporalCoverage.EXACT,
        fallback_policy=fallback_policy,
        fallback_source_ids=fallback_source_ids,
    )


def test_registry_lookup_and_official_fallback_targets() -> None:
    backup = _profile("TEST.BACKUP")
    primary = _profile(
        "TEST.PRIMARY",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.BACKUP",),
    )
    registry = LegalSourceRegistry((primary, backup))

    assert registry.source_ids() == ("TEST.BACKUP", "TEST.PRIMARY")
    assert registry.get("TEST.PRIMARY") is primary
    assert registry.fallback_targets(
        "TEST.PRIMARY",
        required_capability=AuthorityCapability.PUBLICATION_IDENTITY,
    ) == (backup,)


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
        source_classes=(SourceClass.DERIVED_OPEN_SOURCE,),
        authority_capabilities=(AuthorityCapability.DISCOVERY,),
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


def test_registry_accepts_discovery_only_target_with_discovery_capability() -> None:
    discovery = _profile(
        "TEST.DISCOVERY",
        source_classes=(SourceClass.DERIVED_OPEN_SOURCE,),
        authority_capabilities=(AuthorityCapability.DISCOVERY,),
    )
    primary = _profile(
        "TEST.PRIMARY.DISCOVERY",
        fallback_policy=FallbackPolicy.DISCOVERY_ONLY,
        fallback_source_ids=("TEST.DISCOVERY",),
    )

    registry = LegalSourceRegistry((primary, discovery))

    assert registry.fallback_targets(
        "TEST.PRIMARY.DISCOVERY",
        required_capability=AuthorityCapability.DISCOVERY,
    ) == (discovery,)


def test_registry_rejects_discovery_only_target_without_discovery_capability() -> None:
    target = _profile("TEST.NOT-DISCOVERY")
    primary = _profile(
        "TEST.PRIMARY.NO-DISCOVERY",
        fallback_policy=FallbackPolicy.DISCOVERY_ONLY,
        fallback_source_ids=("TEST.NOT-DISCOVERY",),
    )

    with pytest.raises(LegalAuthorityContractError):
        LegalSourceRegistry((primary, target))


def test_fallback_target_must_support_requested_capability() -> None:
    backup = _profile(
        "TEST.BACKUP.CITATION",
        source_classes=(SourceClass.OFFICIAL_OPEN_DATA,),
        authority_capabilities=(AuthorityCapability.CITATION_METADATA,),
    )
    primary = _profile(
        "TEST.PRIMARY.CAPABILITY",
        fallback_policy=FallbackPolicy.OFFICIAL_ONLY,
        fallback_source_ids=("TEST.BACKUP.CITATION",),
    )
    registry = LegalSourceRegistry((primary, backup))

    with pytest.raises(LegalAuthorityContractError):
        registry.fallback_targets(
            "TEST.PRIMARY.CAPABILITY",
            required_capability=AuthorityCapability.NORM_TEXT,
        )
