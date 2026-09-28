"""Static project registry, separate from live state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from core.p3.contracts import content_digest

from .config_validation import (
    require_bool,
    require_nonnegative_int,
    require_string,
    require_string_list,
)
from .contracts import NightShiftContractError, RiskClass


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    project_id: str
    repository: str
    priority: int
    default_risk_class: RiskClass
    required_capabilities: tuple[str, ...]
    mutating: bool

    def __post_init__(self) -> None:
        caps = tuple(sorted({x.strip() for x in self.required_capabilities}))
        if (
            not self.project_id.strip()
            or not self.repository.strip()
            or self.priority < 0
            or not caps
        ):
            raise NightShiftContractError("invalid project config")
        object.__setattr__(self, "required_capabilities", caps)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "repository": self.repository,
            "priority": self.priority,
            "default_risk_class": self.default_risk_class.value,
            "required_capabilities": list(self.required_capabilities),
            "mutating": self.mutating,
        }


@dataclass(frozen=True, slots=True)
class ProjectRegistry:
    projects: tuple[ProjectConfig, ...]

    def __post_init__(self) -> None:
        if len({x.project_id for x in self.projects}) != len(self.projects) or len(
            {x.repository for x in self.projects}
        ) != len(self.projects):
            raise NightShiftContractError("project registry identities must be unique")

    def by_project_id(self, project_id: str) -> ProjectConfig:
        matches = [x for x in self.projects if x.project_id == project_id]
        if len(matches) != 1:
            raise NightShiftContractError("project not uniquely registered")
        return matches[0]

    def digest(self) -> str:
        return content_digest({"projects": [item.canonical_dict() for item in self.projects]})


def load_project_registry(path: str | Path) -> ProjectRegistry:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("projects"), list):
        raise NightShiftContractError("project registry must contain projects")
    return ProjectRegistry(
        tuple(
            sorted(
                (
                    ProjectConfig(
                        require_string(x["project_id"], field_name="project_id"),
                        require_string(x["repository"], field_name="repository"),
                        require_nonnegative_int(x["priority"], field_name="priority"),
                        RiskClass(str(x["default_risk_class"])),
                        require_string_list(
                            x["required_capabilities"],
                            field_name="required_capabilities",
                        ),
                        require_bool(x["mutating"], field_name="mutating"),
                    )
                    for x in raw["projects"]
                ),
                key=lambda x: x.project_id,
            )
        )
    )
