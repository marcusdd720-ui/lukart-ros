"""E7 observability/SRE contracts with privacy-first export."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .contracts import EnterpriseContractError

_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "private_key",
    "pesel",
    "email",
    "phone",
)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LONG_NUMBER = re.compile(r"\b[0-9]{9,19}\b")


def redact_value(key: str, value: object, *, max_length: int = 256) -> str:
    lowered = key.lower()
    if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    text = str(value)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _LONG_NUMBER.sub("[REDACTED_NUMBER]", text)
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    name: str
    trace_id: str
    attributes: Mapping[str, str]

    def digest(self) -> str:
        return content_digest(
            {
                "name": self.name,
                "trace_id": self.trace_id,
                "attributes": dict(sorted(self.attributes.items())),
            }
        )

    def as_otel_attributes(self) -> dict[str, str]:
        """Return a flat attribute mapping suitable for an OpenTelemetry span/event adapter."""
        return dict(self.attributes)


class RedactingTelemetrySink:
    def __init__(self, *, max_attributes: int = 32, max_value_length: int = 256) -> None:
        if max_attributes < 1 or max_value_length < 16:
            raise EnterpriseContractError("invalid telemetry bounds")
        self.max_attributes = max_attributes
        self.max_value_length = max_value_length
        self._events: list[TelemetryEvent] = []

    def emit(
        self,
        name: str,
        attributes: Mapping[str, object],
        *,
        correlation_id: str,
    ) -> TelemetryEvent:
        name = name.strip()
        correlation_id = correlation_id.strip()
        if not name or not correlation_id:
            raise EnterpriseContractError("telemetry name and correlation_id are required")
        if len(attributes) > self.max_attributes:
            raise EnterpriseContractError("telemetry attribute cardinality limit exceeded")
        redacted = {
            str(key): redact_value(str(key), value, max_length=self.max_value_length)
            for key, value in sorted(attributes.items(), key=lambda item: str(item[0]))
        }
        event = TelemetryEvent(
            name=name,
            trace_id=content_digest({"correlation_id": correlation_id})[:32],
            attributes=redacted,
        )
        self._events.append(event)
        return event

    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)


class SliDirection(StrEnum):
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"


@dataclass(frozen=True, slots=True)
class SliObservation:
    metric: str
    value: float


@dataclass(frozen=True, slots=True)
class SloPolicy:
    metric: str
    threshold: float
    direction: SliDirection


@dataclass(frozen=True, slots=True)
class SloResult:
    metric: str
    passed: bool
    observed: float | None
    threshold: float
    reason: str


class SloEvaluator:
    def evaluate(
        self,
        policies: Sequence[SloPolicy],
        observations: Sequence[SliObservation],
    ) -> tuple[SloResult, ...]:
        observed = {item.metric: item.value for item in observations}
        if len(observed) != len(observations):
            raise EnterpriseContractError("duplicate SLI observation")
        policy_metrics = [policy.metric for policy in policies]
        if len(set(policy_metrics)) != len(policy_metrics):
            raise EnterpriseContractError("duplicate SLO policy")

        results: list[SloResult] = []
        for policy in policies:
            value = observed.get(policy.metric)
            if value is None:
                results.append(
                    SloResult(
                        metric=policy.metric,
                        passed=False,
                        observed=None,
                        threshold=policy.threshold,
                        reason="missing SLI evidence",
                    )
                )
                continue
            if policy.direction is SliDirection.LOWER_IS_BETTER:
                passed = value <= policy.threshold
            else:
                passed = value >= policy.threshold
            results.append(
                SloResult(
                    metric=policy.metric,
                    passed=passed,
                    observed=value,
                    threshold=policy.threshold,
                    reason="within SLO" if passed else "SLO threshold violated",
                )
            )
        return tuple(results)
