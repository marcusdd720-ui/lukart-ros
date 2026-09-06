"""P3-10 plugin SDK and fail-closed logical isolation boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.p2.runtime import Plugin

from .contracts import P3ContractError, content_digest, require_unique_nonblank


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    version: str
    capabilities: tuple[str, ...]
    api_version: str
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.plugin_id.strip() or not self.version.strip() or not self.api_version.strip():
            raise P3ContractError("plugin id, version and API version are required")
        capabilities = tuple(
            sorted(require_unique_nonblank(self.capabilities, field_name="capabilities"))
        )
        permissions = tuple(
            sorted(require_unique_nonblank(self.permissions, field_name="permissions"))
        )
        dependencies = tuple(
            sorted(require_unique_nonblank(self.dependencies, field_name="dependencies"))
        )
        if not capabilities:
            raise P3ContractError("plugin must declare at least one capability")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "permissions", permissions)
        object.__setattr__(self, "dependencies", dependencies)

    @property
    def identity(self) -> str:
        return f"{self.plugin_id}@{self.version}"

    def digest(self) -> str:
        return content_digest(
            {
                "plugin_id": self.plugin_id,
                "version": self.version,
                "capabilities": self.capabilities,
                "api_version": self.api_version,
                "permissions": self.permissions,
                "dependencies": self.dependencies,
            }
        )


@dataclass(frozen=True, slots=True)
class PluginCompatibility:
    compatible: bool
    reasons: tuple[str, ...]


class PluginSdkBoundary:
    """Logical permission/API boundary; not an OS/process sandbox."""

    isolation_level = "logical-manifest-boundary"

    def __init__(
        self,
        *,
        host_api_version: str,
        allowed_permissions: Sequence[str],
        allowed_dependencies: Sequence[str] = (),
    ) -> None:
        self.host_api_version = host_api_version.strip()
        if not self.host_api_version:
            raise P3ContractError("host API version is required")
        self.allowed_permissions = frozenset(
            require_unique_nonblank(allowed_permissions, field_name="allowed_permissions")
        )
        self.allowed_dependencies = frozenset(
            require_unique_nonblank(allowed_dependencies, field_name="allowed_dependencies")
        )

    def check(self, manifest: PluginManifest, provider: type[Plugin]) -> PluginCompatibility:
        reasons: list[str] = []
        if manifest.plugin_id != provider.plugin_id or manifest.version != provider.version:
            reasons.append("provider_identity_mismatch")
        if frozenset(manifest.capabilities) != provider.capabilities:
            reasons.append("capability_manifest_mismatch")
        if manifest.api_version != self.host_api_version:
            reasons.append("api_version_mismatch")
        denied_permissions = sorted(set(manifest.permissions) - self.allowed_permissions)
        if denied_permissions:
            reasons.append("permissions_denied:" + ",".join(denied_permissions))
        denied_dependencies = sorted(set(manifest.dependencies) - self.allowed_dependencies)
        if denied_dependencies:
            reasons.append("dependencies_denied:" + ",".join(denied_dependencies))
        return PluginCompatibility(not reasons, tuple(reasons))


class IsolatedPluginRegistry:
    """Class-only registry with immutable manifest binding."""

    def __init__(self, boundary: PluginSdkBoundary) -> None:
        self._boundary = boundary
        self._providers: dict[str, type[Plugin]] = {}
        self._manifests: dict[str, PluginManifest] = {}

    def register(self, provider: type[Plugin], manifest: PluginManifest) -> None:
        compatibility = self._boundary.check(manifest, provider)
        if not compatibility.compatible:
            raise P3ContractError("plugin rejected: " + ";".join(compatibility.reasons))
        identity = provider.identity()
        if identity in self._providers:
            raise P3ContractError(f"duplicate plugin identity: {identity}")
        self._providers[identity] = provider
        self._manifests[identity] = manifest

    def providers(self) -> tuple[type[Plugin], ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))

    def manifests(self) -> Mapping[str, PluginManifest]:
        return dict(sorted(self._manifests.items()))

    def by_capability(self, capability: str) -> tuple[type[Plugin], ...]:
        capability = capability.strip()
        if not capability:
            raise P3ContractError("capability is required")
        return tuple(
            provider
            for provider in self.providers()
            if capability in provider.capabilities
        )

    def registry_digest(self) -> str:
        return content_digest(
            {
                identity: manifest.digest()
                for identity, manifest in sorted(self._manifests.items())
            }
        )
