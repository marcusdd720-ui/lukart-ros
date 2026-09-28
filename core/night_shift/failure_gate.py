"""Content-addressed failure-injection evidence gate for Night Shift."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError, require_git_oid


class FailureOutcome(StrEnum):
    RECOVERED = "RECOVERED"
    FAILED_CLOSED = "FAILED_CLOSED"
    UNSAFE = "UNSAFE"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class FailureInjectionEvidence:
    scenario: str
    outcome: FailureOutcome
    evidence_ref: str
    evidence_digest: str

    def __post_init__(self) -> None:
        scenario = self.scenario.strip()
        evidence_ref = self.evidence_ref.strip()
        if not scenario or not evidence_ref:
            raise NightShiftContractError(
                "failure-injection evidence must be nonblank"
            )
        object.__setattr__(self, "scenario", scenario)
        object.__setattr__(self, "evidence_ref", evidence_ref)
        object.__setattr__(
            self,
            "evidence_digest",
            _digest(self.evidence_digest, field_name="evidence_digest"),
        )

    @property
    def passed(self) -> bool:
        return self.outcome in {
            FailureOutcome.RECOVERED,
            FailureOutcome.FAILED_CLOSED,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "outcome": self.outcome.value,
            "evidence_ref": self.evidence_ref,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True, slots=True)
class FailureInjectionReport:
    subject_sha: str
    state_snapshot_digest: str
    task_capsule_digest: str
    policy_digest: str
    suite_profile_digest: str
    generated_at_epoch: int
    expires_at_epoch: int
    evidence: tuple[FailureInjectionEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        object.__setattr__(
            self,
            "state_snapshot_digest",
            _digest(
                self.state_snapshot_digest,
                field_name="state_snapshot_digest",
            ),
        )
        object.__setattr__(
            self,
            "task_capsule_digest",
            _digest(
                self.task_capsule_digest,
                field_name="task_capsule_digest",
            ),
        )
        object.__setattr__(
            self,
            "policy_digest",
            _digest(self.policy_digest, field_name="policy_digest"),
        )
        object.__setattr__(
            self,
            "suite_profile_digest",
            _digest(
                self.suite_profile_digest,
                field_name="suite_profile_digest",
            ),
        )
        if self.generated_at_epoch < 0:
            raise NightShiftContractError(
                "failure report generation time cannot be negative"
            )
        if self.expires_at_epoch <= self.generated_at_epoch:
            raise NightShiftContractError(
                "failure report expiry must follow generation"
            )
        ordered = tuple(sorted(self.evidence, key=lambda item: item.scenario))
        names = [item.scenario for item in ordered]
        if len(names) != len(set(names)):
            raise NightShiftContractError(
                "duplicate failure-injection scenario"
            )
        object.__setattr__(self, "evidence", ordered)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-failure-injection-report/v2",
            "subject_sha": self.subject_sha,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "policy_digest": self.policy_digest,
            "suite_profile_digest": self.suite_profile_digest,
            "generated_at_epoch": self.generated_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
            "evidence": [item.canonical_dict() for item in self.evidence],
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())

    def require_passed(
        self,
        *,
        required_scenarios: tuple[str, ...],
        expected_subject_sha: str,
        expected_state_snapshot_digest: str,
        expected_task_capsule_digest: str,
        expected_policy_digest: str,
        expected_suite_profile_digest: str,
        now_epoch: int,
        expected_report_digest: str | None = None,
    ) -> None:
        required = tuple(sorted({item.strip() for item in required_scenarios}))
        if not required or any(not item for item in required):
            raise NightShiftContractError(
                "required failure-injection scenarios are invalid"
            )
        expected_sha = require_git_oid(
            expected_subject_sha,
            field_name="expected_subject_sha",
        )
        if self.subject_sha != expected_sha:
            raise NightShiftContractError(
                "failure report belongs to a different subject SHA"
            )
        expected_state = _digest(
            expected_state_snapshot_digest,
            field_name="expected_state_snapshot_digest",
        )
        if self.state_snapshot_digest != expected_state:
            raise NightShiftContractError(
                "failure report belongs to a different state snapshot"
            )
        expected_task = _digest(
            expected_task_capsule_digest,
            field_name="expected_task_capsule_digest",
        )
        if self.task_capsule_digest != expected_task:
            raise NightShiftContractError(
                "failure report belongs to a different task capsule"
            )
        if self.policy_digest != _digest(
            expected_policy_digest,
            field_name="expected_policy_digest",
        ):
            raise NightShiftContractError(
                "failure report belongs to a different policy"
            )
        if self.suite_profile_digest != _digest(
            expected_suite_profile_digest,
            field_name="expected_suite_profile_digest",
        ):
            raise NightShiftContractError(
                "failure report belongs to a different suite profile"
            )
        if now_epoch < self.generated_at_epoch:
            raise NightShiftContractError(
                "current time precedes failure report generation"
            )
        if now_epoch >= self.expires_at_epoch:
            raise NightShiftContractError("failure report expired")
        if expected_report_digest is not None:
            expected = _digest(
                expected_report_digest,
                field_name="expected_failure_report_digest",
            )
            if self.digest() != expected:
                raise NightShiftContractError(
                    "failure report digest does not match expected authority"
                )

        by_name = {item.scenario: item for item in self.evidence}
        missing = [item for item in required if item not in by_name]
        if missing:
            raise NightShiftContractError(
                "failure-injection evidence incomplete: " + ",".join(missing)
            )
        unexpected = sorted(set(by_name) - set(required))
        if unexpected:
            raise NightShiftContractError(
                "failure-injection evidence contains unexpected scenarios: "
                + ",".join(unexpected)
            )
        unsafe = [item for item in required if not by_name[item].passed]
        if unsafe:
            raise NightShiftContractError(
                "failure-injection scenario unsafe: " + ",".join(unsafe)
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
        raise NightShiftContractError(
            "failure_injection.scenarios must be a list"
        )
    normalized = tuple(sorted({str(item).strip() for item in scenarios}))
    if (
        not normalized
        or len(normalized) != len(scenarios)
        or any(not item for item in normalized)
    ):
        raise NightShiftContractError(
            "failure_injection.scenarios are invalid"
        )
    return normalized

def load_failure_suite_max_age_seconds(path: str | Path) -> int:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise NightShiftContractError(
            "failure-injection profile must be a mapping"
        )
    freshness = raw.get("freshness")
    if not isinstance(freshness, dict):
        raise NightShiftContractError(
            "failure-injection profile must contain freshness"
        )
    value = freshness.get("max_report_age_seconds")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise NightShiftContractError(
            "max_report_age_seconds must be a positive integer"
        )
    return value


def failure_suite_profile_digest(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return content_digest({"failure_suite_profile_text": text})


def load_failure_report(
    path: str | Path,
    *,
    subject_sha: str,
    state_snapshot_digest: str,
    task_capsule_digest: str,
    policy_digest: str,
    suite_profile_digest: str,
    generated_at_epoch: int,
    expires_at_epoch: int,
) -> FailureInjectionReport:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("evidence"), list):
        raise NightShiftContractError(
            "failure evidence manifest must contain evidence"
        )
    items: list[FailureInjectionEvidence] = []
    for item in raw["evidence"]:
        if not isinstance(item, dict):
            raise NightShiftContractError(
                "failure evidence entry must be a mapping"
            )
        scenario = item.get("scenario")
        outcome = item.get("outcome")
        evidence_ref = item.get("evidence_ref")
        evidence_digest = item.get("evidence_digest")
        if not isinstance(scenario, str):
            raise NightShiftContractError(
                "failure evidence scenario must be a string"
            )
        if not isinstance(outcome, str):
            raise NightShiftContractError(
                "failure evidence outcome must be a string"
            )
        if not isinstance(evidence_ref, str):
            raise NightShiftContractError(
                "failure evidence reference must be a string"
            )
        if not isinstance(evidence_digest, str):
            raise NightShiftContractError(
                "failure evidence digest must be a string"
            )
        try:
            parsed_outcome = FailureOutcome(outcome)
        except ValueError as exc:
            raise NightShiftContractError(
                "failure evidence outcome is invalid"
            ) from exc
        items.append(
            FailureInjectionEvidence(
                scenario=scenario,
                outcome=parsed_outcome,
                evidence_ref=evidence_ref,
                evidence_digest=evidence_digest,
            )
        )
    return FailureInjectionReport(
        subject_sha=subject_sha,
        state_snapshot_digest=state_snapshot_digest,
        task_capsule_digest=task_capsule_digest,
        policy_digest=policy_digest,
        suite_profile_digest=suite_profile_digest,
        generated_at_epoch=generated_at_epoch,
        expires_at_epoch=expires_at_epoch,
        evidence=tuple(items),
    )
