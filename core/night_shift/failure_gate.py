"""Failure-injection evidence gate required before controlled canaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class FailureInjectionEvidence:
    scenario: str
    passed: bool
    evidence_ref: str

    def __post_init__(self) -> None:
        scenario = self.scenario.strip()
        evidence_ref = self.evidence_ref.strip()
        if not scenario or not evidence_ref:
            raise NightShiftContractError("failure-injection evidence must be nonblank")
        object.__setattr__(self, "scenario", scenario)
        object.__setattr__(self, "evidence_ref", evidence_ref)


@dataclass(frozen=True, slots=True)
class FailureInjectionReport:
    evidence: tuple[FailureInjectionEvidence, ...]

    def require_passed(self, *, required_scenarios: tuple[str, ...]) -> None:
        required = tuple(sorted({item.strip() for item in required_scenarios}))
        if not required or any(not item for item in required):
            raise NightShiftContractError("required failure-injection scenarios are invalid")
        by_name: dict[str, FailureInjectionEvidence] = {}
        for item in self.evidence:
            if item.scenario in by_name:
                raise NightShiftContractError("duplicate failure-injection scenario")
            by_name[item.scenario] = item
        missing = [item for item in required if item not in by_name]
        if missing:
            raise NightShiftContractError(
                "failure-injection evidence incomplete: " + ",".join(missing)
            )
        failed = [item for item in required if not by_name[item].passed]
        if failed:
            raise NightShiftContractError(
                "failure-injection scenario failed: " + ",".join(failed)
            )


def load_required_failure_scenarios(path: str | Path) -> tuple[str, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    try:
        scenarios = raw["failure_injection"]["scenarios"]
    except (KeyError, TypeError) as exc:
        raise NightShiftContractError(
            "policy is missing failure_injection.scenarios"
        ) from exc
    if not isinstance(scenarios, list):
        raise NightShiftContractError("failure_injection.scenarios must be a list")
    normalized = tuple(sorted({str(item).strip() for item in scenarios}))
    if not normalized or len(normalized) != len(scenarios) or any(not item for item in normalized):
        raise NightShiftContractError("failure_injection.scenarios are invalid")
    return normalized


def load_failure_report(path: str | Path) -> FailureInjectionReport:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("evidence"), list):
        raise NightShiftContractError("failure evidence manifest must contain evidence")
    items: list[FailureInjectionEvidence] = []
    for item in raw["evidence"]:
        if not isinstance(item, dict):
            raise NightShiftContractError("failure evidence entry must be a mapping")
        passed = item.get("passed")
        if not isinstance(passed, bool):
            raise NightShiftContractError("failure evidence passed must be boolean")
        scenario = item.get("scenario")
        evidence_ref = item.get("evidence_ref")
        if not isinstance(scenario, str) or not isinstance(evidence_ref, str):
            raise NightShiftContractError("failure evidence fields must be strings")
        items.append(FailureInjectionEvidence(scenario, passed, evidence_ref))
    return FailureInjectionReport(tuple(items))
