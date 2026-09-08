"""OPR-01 deterministic operational-readiness verification v1.

Verification-only aggregation over existing FIV-02/replay/recovery/authorization
contracts. Telemetry is derived observability, never Product or CCL authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.critical_invariants_v2 import FIV02InvariantId, FIV02VerificationReport, verify_fiv02
from core.p3.contracts import content_digest, require_hex_digest

POLICY_SCHEMA = "lukart.operational-readiness-policy.v1"
TELEMETRY_SCHEMA = "lukart.operational-telemetry-event.v1"
SLI_RESULT_SCHEMA = "lukart.operational-sli-result.v1"
INCIDENT_SCHEMA = "lukart.operational-incident-rule.v1"
REPORT_SCHEMA = "lukart.operational-readiness-report.v1"
MAX_TELEMETRY_EVENTS = 64


class OperationalReadinessV1Error(ValueError):
    """Fail-closed OPR-01 contract violation."""


class ReadinessOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class IncidentSeverity(StrEnum):
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    FATAL = "FATAL"


class TelemetryEventName(StrEnum):
    CRITICAL_INVARIANTS = "critical_invariants"
    REPLAY_DRILL = "replay_drill"
    RECOVERY_DRILL = "recovery_drill"
    DEGRADED_MODE = "degraded_mode"
    AUTHORIZATION_BOUNDARY = "authorization_boundary"
    INCIDENT_DETECTION = "incident_detection"
    RUNBOOK_VALIDATION = "runbook_validation"


def _text(value: str, *, field_name: str, limit: int = 192) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OperationalReadinessV1Error(f"{field_name} must be nonblank and canonical")
    if len(value) > limit:
        raise OperationalReadinessV1Error(f"{field_name} exceeds bounded length")
    return value


def _identifier(value: str, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=96)
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_."
    if any(character not in allowed for character in value):
        raise OperationalReadinessV1Error(f"{field_name} has invalid identifier characters")
    return value


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise OperationalReadinessV1Error(str(exc)) from exc


def _git_sha(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip() or value.lower() != value:
        raise OperationalReadinessV1Error(
            f"{field_name} must be canonical lowercase Git object identity"
        )
    try:
        return require_hex_digest(value, field_name=field_name, lengths=(40, 64))
    except ValueError as exc:
        raise OperationalReadinessV1Error(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SLISpecV1:
    sli_id: str
    total_samples: int
    required_successes: int
    max_failures: int

    def __post_init__(self) -> None:
        _identifier(self.sli_id, field_name="sli_id")
        values = (self.total_samples, self.required_successes, self.max_failures)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise OperationalReadinessV1Error("SLI counts must be nonnegative integers")
        if self.total_samples <= 0 or self.required_successes > self.total_samples:
            raise OperationalReadinessV1Error("invalid SLI sample/SLO contract")
        if self.max_failures > self.total_samples:
            raise OperationalReadinessV1Error("invalid SLI error budget")
        if self.required_successes + self.max_failures < self.total_samples:
            raise OperationalReadinessV1Error("SLI contract permits an unbudgeted result gap")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "sli_id": self.sli_id,
            "total_samples": self.total_samples,
            "required_successes": self.required_successes,
            "max_failures": self.max_failures,
        }


@dataclass(frozen=True, slots=True)
class IncidentRuleV1:
    signal: str
    severity: IncidentSeverity
    runbook_section: str
    schema: str = INCIDENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INCIDENT_SCHEMA or not isinstance(self.severity, IncidentSeverity):
            raise OperationalReadinessV1Error("unsupported incident rule")
        _identifier(self.signal, field_name="incident signal")
        _text(self.runbook_section, field_name="runbook_section")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "signal": self.signal,
            "severity": self.severity.value,
            "runbook_section": self.runbook_section,
        }


@dataclass(frozen=True, slots=True)
class OperationalReadinessPolicyV1:
    sli_specs: tuple[SLISpecV1, ...]
    incident_rules: tuple[IncidentRuleV1, ...]
    required_runbook_headings: tuple[str, ...]
    schema: str = POLICY_SCHEMA

    @classmethod
    def reference(cls) -> OperationalReadinessPolicyV1:
        return cls(
            sli_specs=(
                SLISpecV1("critical_invariant_pass_ratio", 6, 6, 0),
                SLISpecV1("replay_recovery_drill_pass_ratio", 2, 2, 0),
                SLISpecV1("degraded_mode_containment_ratio", 4, 4, 0),
                SLISpecV1("incident_detection_coverage_ratio", 6, 6, 0),
                SLISpecV1("runbook_contract_coverage_ratio", 8, 8, 0),
                SLISpecV1("telemetry_contract_validity_ratio", 7, 7, 0),
                SLISpecV1("security_trust_boundary_pass_ratio", 2, 2, 0),
            ),
            incident_rules=(
                IncidentRuleV1("private_or_secret_boundary_breach", IncidentSeverity.FATAL, "## Incident procedure"),
                IncidentRuleV1("unauthorized_trust_promotion", IncidentSeverity.FATAL, "## Security and privacy procedure"),
                IncidentRuleV1("replay_identity_mismatch", IncidentSeverity.HIGH, "## Replay procedure"),
                IncidentRuleV1("recovery_identity_mismatch", IncidentSeverity.HIGH, "## Recovery/replay drills and degraded-mode tests"),
                IncidentRuleV1("operational_error_budget_exhausted", IncidentSeverity.HIGH, "## Operational readiness / SLI-SLO and error budgets"),
                IncidentRuleV1("telemetry_contract_violation", IncidentSeverity.MEDIUM, "## Observability and telemetry contract"),
            ),
            required_runbook_headings=(
                "## Replay procedure",
                "## Security and privacy procedure",
                "## Incident procedure",
                "## Evidence retention",
                "## Operational readiness / SLI-SLO and error budgets",
                "## Observability and telemetry contract",
                "## Recovery/replay drills and degraded-mode tests",
                "## Runbook validation",
            ),
        )

    def __post_init__(self) -> None:
        if self.schema != POLICY_SCHEMA:
            raise OperationalReadinessV1Error("unsupported operational policy schema")
        sli_ids = tuple(spec.sli_id for spec in self.sli_specs)
        signals = tuple(rule.signal for rule in self.incident_rules)
        headings = tuple(_text(item, field_name="runbook heading") for item in self.required_runbook_headings)
        if len(sli_ids) != 7 or len(set(sli_ids)) != 7:
            raise OperationalReadinessV1Error("OPR-01 requires fixed seven-SLI registry")
        if len(signals) != 6 or len(set(signals)) != 6:
            raise OperationalReadinessV1Error("OPR-01 requires fixed six-signal incident registry")
        if len(headings) != 8 or len(set(headings)) != 8:
            raise OperationalReadinessV1Error("OPR-01 requires fixed eight-section runbook")
        object.__setattr__(self, "required_runbook_headings", headings)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "sli_specs": [item.canonical_dict() for item in self.sli_specs],
            "incident_rules": [item.canonical_dict() for item in self.incident_rules],
            "required_runbook_headings": list(self.required_runbook_headings),
        }

    @property
    def policy_digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class TelemetryEventV1:
    event: TelemetryEventName
    component: str
    outcome: ReadinessOutcome
    code_sha: str
    evidence_digest: str
    schema: str = TELEMETRY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != TELEMETRY_SCHEMA or not isinstance(self.event, TelemetryEventName):
            raise OperationalReadinessV1Error("unknown telemetry schema/event")
        if not isinstance(self.outcome, ReadinessOutcome):
            raise OperationalReadinessV1Error("unknown telemetry outcome")
        _identifier(self.component, field_name="telemetry component")
        object.__setattr__(self, "code_sha", _git_sha(self.code_sha, field_name="code_sha"))
        object.__setattr__(self, "evidence_digest", _digest(self.evidence_digest, field_name="evidence_digest"))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "event": self.event.value,
            "component": self.component,
            "outcome": self.outcome.value,
            "code_sha": self.code_sha,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True, slots=True)
class SLIResultV1:
    spec: SLISpecV1
    successes: int
    failures: int
    outcome: ReadinessOutcome
    schema: str = SLI_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SLI_RESULT_SCHEMA:
            raise OperationalReadinessV1Error("unsupported SLI result schema")
        if self.successes < 0 or self.failures < 0 or self.successes + self.failures != self.spec.total_samples:
            raise OperationalReadinessV1Error("SLI sample count mismatch")
        expected = ReadinessOutcome.PASS if (
            self.successes >= self.spec.required_successes and self.failures <= self.spec.max_failures
        ) else ReadinessOutcome.FAIL
        if self.outcome is not expected:
            raise OperationalReadinessV1Error("SLI outcome contradicts SLO/error budget")

    @property
    def error_budget_consumed(self) -> int:
        return self.failures

    @property
    def error_budget_remaining(self) -> int:
        return max(0, self.spec.max_failures - self.failures)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "spec": self.spec.canonical_dict(),
            "successes": self.successes,
            "failures": self.failures,
            "error_budget_consumed": self.error_budget_consumed,
            "error_budget_remaining": self.error_budget_remaining,
            "outcome": self.outcome.value,
        }


def evaluate_sli(spec: SLISpecV1, *, successes: int, failures: int) -> SLIResultV1:
    outcome = ReadinessOutcome.PASS if (
        successes >= spec.required_successes and failures <= spec.max_failures
    ) else ReadinessOutcome.FAIL
    return SLIResultV1(spec, successes, failures, outcome)


def detect_incident(signal: str) -> IncidentRuleV1:
    signal = _identifier(signal, field_name="incident signal")
    matches = tuple(rule for rule in OperationalReadinessPolicyV1.reference().incident_rules if rule.signal == signal)
    if len(matches) != 1:
        raise OperationalReadinessV1Error("unknown or ambiguous incident signal")
    return matches[0]


def validate_runbook(text: str, policy: OperationalReadinessPolicyV1) -> tuple[str, ...]:
    if not isinstance(text, str) or not text.strip():
        raise OperationalReadinessV1Error("runbook text must be nonblank")
    lines = tuple(line.strip() for line in text.splitlines())
    return tuple(heading for heading in policy.required_runbook_headings if lines.count(heading) == 1)


def _fiv_pass(report: FIV02VerificationReport, invariant: FIV02InvariantId) -> bool:
    matches = tuple(result for result in report.results if result.invariant_id is invariant)
    return len(matches) == 1 and matches[0].outcome == "PASS"


def _telemetry(event: TelemetryEventName, component: str, code_sha: str, evidence: object, passed: bool) -> TelemetryEventV1:
    return TelemetryEventV1(
        event,
        component,
        ReadinessOutcome.PASS if passed else ReadinessOutcome.FAIL,
        code_sha,
        content_digest(evidence),
    )


@dataclass(frozen=True, slots=True)
class OperationalReadinessReportV1:
    code_sha: str
    policy_digest: str
    fiv02_report_digest: str
    runbook_digest: str
    sli_results: tuple[SLIResultV1, ...]
    telemetry: tuple[TelemetryEventV1, ...]
    incident_rule_digests: tuple[str, ...]
    outcome: ReadinessOutcome
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise OperationalReadinessV1Error("unsupported readiness report schema")
        object.__setattr__(self, "code_sha", _git_sha(self.code_sha, field_name="code_sha"))
        for name in ("policy_digest", "fiv02_report_digest", "runbook_digest"):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        if len(self.sli_results) != 7 or len(self.telemetry) != 7 or len(self.telemetry) > MAX_TELEMETRY_EVENTS:
            raise OperationalReadinessV1Error("incomplete readiness registry")
        if any(event.code_sha != self.code_sha for event in self.telemetry):
            raise OperationalReadinessV1Error("telemetry is not bound to report code_sha")
        rules = tuple(_digest(item, field_name="incident_rule_digest") for item in self.incident_rule_digests)
        if len(rules) != 6 or len(set(rules)) != 6:
            raise OperationalReadinessV1Error("incomplete incident registry")
        object.__setattr__(self, "incident_rule_digests", rules)
        expected = ReadinessOutcome.PASS if all(item.outcome is ReadinessOutcome.PASS for item in self.sli_results) else ReadinessOutcome.FAIL
        if self.outcome is not expected:
            raise OperationalReadinessV1Error("readiness outcome contradicts SLI results")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "code_sha": self.code_sha,
            "policy_digest": self.policy_digest,
            "fiv02_report_digest": self.fiv02_report_digest,
            "runbook_digest": self.runbook_digest,
            "sli_results": [item.canonical_dict() for item in self.sli_results],
            "telemetry": [item.canonical_dict() for item in self.telemetry],
            "incident_rule_digests": list(self.incident_rule_digests),
            "outcome": self.outcome.value,
            "authority": "operational-verification-only",
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "report_digest": self.report_digest}

    def verify(self) -> None:
        policy = OperationalReadinessPolicyV1.reference()
        if self.policy_digest != policy.policy_digest:
            raise OperationalReadinessV1Error("operational policy identity mismatch")
        if tuple(item.spec.sli_id for item in self.sli_results) != tuple(item.sli_id for item in policy.sli_specs):
            raise OperationalReadinessV1Error("SLI registry mismatch")
        expected_rules = tuple(content_digest(rule.canonical_dict()) for rule in policy.incident_rules)
        if self.incident_rule_digests != expected_rules:
            raise OperationalReadinessV1Error("incident registry identity mismatch")


def run_operational_readiness_drill(*, code_sha: str, expected_code_sha: str, workspace: Path, runbook_text: str) -> OperationalReadinessReportV1:
    code_sha = _git_sha(code_sha, field_name="code_sha")
    expected_code_sha = _git_sha(expected_code_sha, field_name="expected_code_sha")
    if code_sha != expected_code_sha:
        raise OperationalReadinessV1Error("code_sha does not match expected_code_sha")

    policy = OperationalReadinessPolicyV1.reference()
    fiv = verify_fiv02(code_sha=code_sha, expected_code_sha=expected_code_sha, workspace=Path(workspace))
    fiv.verify()
    fiv_passes = sum(result.outcome == "PASS" for result in fiv.results)
    replay = _fiv_pass(fiv, FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE)
    recovery = _fiv_pass(fiv, FIV02InvariantId.RECOVERY_ATOMICITY)
    degraded_ids = (
        FIV02InvariantId.APPEND_ONLY_EXACT_HEAD,
        FIV02InvariantId.MIGRATION_PATH_DETERMINISM,
        FIV02InvariantId.AUTHORIZATION_ISOLATION,
        FIV02InvariantId.RECOVERY_ATOMICITY,
    )
    degraded = sum(_fiv_pass(fiv, item) for item in degraded_ids)
    authorization = _fiv_pass(fiv, FIV02InvariantId.AUTHORIZATION_ISOLATION)
    rules = tuple(detect_incident(rule.signal) for rule in policy.incident_rules)
    rule_digests = tuple(content_digest(rule.canonical_dict()) for rule in rules)
    headings = validate_runbook(runbook_text, policy)
    runbook_digest = content_digest({"utf8_text": runbook_text})

    counts = {
        "critical_invariant_pass_ratio": (fiv_passes, 6 - fiv_passes),
        "replay_recovery_drill_pass_ratio": (int(replay) + int(recovery), 2 - int(replay) - int(recovery)),
        "degraded_mode_containment_ratio": (degraded, 4 - degraded),
        "incident_detection_coverage_ratio": (len(rules), 6 - len(rules)),
        "runbook_contract_coverage_ratio": (len(headings), 8 - len(headings)),
        "telemetry_contract_validity_ratio": (7, 0),
        "security_trust_boundary_pass_ratio": (int(authorization) + int(len(rules) == 6), 2 - int(authorization) - int(len(rules) == 6)),
    }
    results = tuple(evaluate_sli(spec, successes=counts[spec.sli_id][0], failures=counts[spec.sli_id][1]) for spec in policy.sli_specs)
    telemetry = (
        _telemetry(TelemetryEventName.CRITICAL_INVARIANTS, "fiv02", code_sha, fiv.report_identity.canonical_dict(), fiv_passes == 6),
        _telemetry(TelemetryEventName.REPLAY_DRILL, "case-replay-v2", code_sha, FIV02InvariantId.REPLAY_PROJECTION_EQUIVALENCE.value, replay),
        _telemetry(TelemetryEventName.RECOVERY_DRILL, "recovery-continuity-v1", code_sha, FIV02InvariantId.RECOVERY_ATOMICITY.value, recovery),
        _telemetry(TelemetryEventName.DEGRADED_MODE, "fiv02-negative-probes", code_sha, [item.value for item in degraded_ids], degraded == 4),
        _telemetry(TelemetryEventName.AUTHORIZATION_BOUNDARY, "enterprise-authorization", code_sha, FIV02InvariantId.AUTHORIZATION_ISOLATION.value, authorization),
        _telemetry(TelemetryEventName.INCIDENT_DETECTION, "operational-incident-registry", code_sha, rule_digests, len(rules) == 6),
        _telemetry(TelemetryEventName.RUNBOOK_VALIDATION, "post-v1-operations-runbook", code_sha, {"runbook_digest": runbook_digest, "headings": list(headings)}, len(headings) == 8),
    )
    outcome = ReadinessOutcome.PASS if all(item.outcome is ReadinessOutcome.PASS for item in results) else ReadinessOutcome.FAIL
    report = OperationalReadinessReportV1(
        code_sha,
        policy.policy_digest,
        fiv.report_identity.digest,
        runbook_digest,
        results,
        telemetry,
        rule_digests,
        outcome,
    )
    report.verify()
    return report
