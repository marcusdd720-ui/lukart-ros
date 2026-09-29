"""Immutable registry for LegalSourceProfile v1."""

from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from .contracts import (
    AuthorityCapability,
    FallbackPolicy,
    LegalAuthorityContractError,
    LegalSourceProfile,
)


class LegalSourceRegistry:
    """Fail-closed registry of legal-source profiles."""

    __slots__ = ("_profiles",)

    def __init__(self, profiles: Iterable[LegalSourceProfile]) -> None:
        indexed: dict[str, LegalSourceProfile] = {}
        for profile in profiles:
            if profile.source_id in indexed:
                raise LegalAuthorityContractError(
                    f"duplicate legal source_id: {profile.source_id}"
                )
            indexed[profile.source_id] = profile

        if not indexed:
            raise LegalAuthorityContractError(
                "legal source registry cannot be empty"
            )

        self._validate_fallbacks(indexed)
        self._profiles = MappingProxyType(dict(sorted(indexed.items())))

    @staticmethod
    def _validate_fallbacks(
        profiles: dict[str, LegalSourceProfile],
    ) -> None:
        for profile in profiles.values():
            for fallback_id in profile.fallback_source_ids:
                target = profiles.get(fallback_id)
                if target is None:
                    raise LegalAuthorityContractError(
                        f"unknown fallback source_id: {fallback_id}"
                    )
                if (
                    profile.fallback_policy is FallbackPolicy.OFFICIAL_ONLY
                    and not target.is_official
                ):
                    raise LegalAuthorityContractError(
                        "OFFICIAL_ONLY fallback must target an official source"
                    )
                if (
                    profile.fallback_policy is FallbackPolicy.DISCOVERY_ONLY
                    and not target.can_establish(AuthorityCapability.DISCOVERY)
                ):
                    raise LegalAuthorityContractError(
                        "DISCOVERY_ONLY fallback must target a discovery-capable source"
                    )

        for source_id in profiles:
            LegalSourceRegistry._assert_no_fallback_cycle(
                source_id,
                profiles=profiles,
                active=(),
            )

    @staticmethod
    def _assert_no_fallback_cycle(
        source_id: str,
        *,
        profiles: dict[str, LegalSourceProfile],
        active: tuple[str, ...],
    ) -> None:
        if source_id in active:
            cycle = " -> ".join((*active, source_id))
            raise LegalAuthorityContractError(
                f"fallback cycle detected: {cycle}"
            )
        profile = profiles[source_id]
        next_active = (*active, source_id)
        for fallback_id in profile.fallback_source_ids:
            LegalSourceRegistry._assert_no_fallback_cycle(
                fallback_id,
                profiles=profiles,
                active=next_active,
            )

    def get(self, source_id: str) -> LegalSourceProfile:
        try:
            return self._profiles[source_id]
        except KeyError as exc:
            raise LegalAuthorityContractError(
                f"unknown legal source_id: {source_id}"
            ) from exc

    def fallback_targets(
        self,
        source_id: str,
        *,
        required_capability: AuthorityCapability,
    ) -> tuple[LegalSourceProfile, ...]:
        profile = self.get(source_id)
        targets = tuple(self.get(item) for item in profile.fallback_source_ids)
        for target in targets:
            if not target.can_establish(required_capability):
                raise LegalAuthorityContractError(
                    f"fallback source {target.source_id} lacks required capability "
                    f"{required_capability.value}"
                )
        return targets

    def source_ids(self) -> tuple[str, ...]:
        return tuple(self._profiles)
