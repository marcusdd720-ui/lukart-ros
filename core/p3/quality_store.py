"""Durable longitudinal KQM storage backed by the P3 provenance ledger."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .contracts import P3ContractError, RuntimeIdentity, content_digest
from .ledger import AppendOnlyReplayLedger
from .operations import LongitudinalQualityStore, MetricObjective, QualityDelta, QualityPoint


class PersistentLongitudinalQualityStore:
    """Tamper-evident append-only KQM history across releases and corpora."""

    _CASE_ID = "@quality"
    _EVENT_TYPE = "KQM_POINT"

    def __init__(
        self,
        path: str | Path,
        *,
        runtime_identity: RuntimeIdentity,
        objectives: Mapping[str, MetricObjective | str],
    ) -> None:
        self._ledger = AppendOnlyReplayLedger(path)
        self._runtime_identity = runtime_identity
        self._objectives = dict(objectives)

    def append(self, point: QualityPoint) -> None:
        existing = {item.release_id for item in self.points()}
        if point.release_id in existing:
            raise P3ContractError(f"duplicate quality release_id: {point.release_id}")
        payload: dict[str, object] = {
            "release_id": point.release_id,
            "code_sha": point.code_sha,
            "corpus_digest": point.corpus_digest,
            "metrics": dict(point.metrics),
            "point_digest": point.digest(),
        }
        self._ledger.append(
            case_id=self._CASE_ID,
            event_type=self._EVENT_TYPE,
            runtime_identity=self._runtime_identity,
            payload=payload,
        )

    def points(self) -> tuple[QualityPoint, ...]:
        result: list[QualityPoint] = []
        for record in self._ledger.verify():
            if record.case_id != self._CASE_ID or record.event_type != self._EVENT_TYPE:
                raise P3ContractError("quality ledger contains foreign event")
            payload = record.payload
            metrics = payload.get("metrics")
            if not isinstance(metrics, dict):
                raise P3ContractError("quality ledger metrics must be an object")
            normalized_metrics: dict[str, float] = {}
            for name, value in metrics.items():
                if not isinstance(name, str) or not isinstance(value, int | float):
                    raise P3ContractError("invalid persisted quality metric")
                normalized_metrics[name] = float(value)
            point = QualityPoint(
                release_id=str(payload.get("release_id", "")),
                code_sha=str(payload.get("code_sha", "")),
                corpus_digest=str(payload.get("corpus_digest", "")),
                metrics=normalized_metrics,
            )
            expected = payload.get("point_digest")
            if not isinstance(expected, str) or expected != point.digest():
                raise P3ContractError("persisted quality point digest mismatch")
            result.append(point)
        return tuple(result)

    def compare(
        self,
        baseline_release: str,
        current_release: str,
    ) -> tuple[QualityDelta, ...]:
        store = LongitudinalQualityStore(self._objectives)
        for point in self.points():
            store.append(point)
        return store.compare(baseline_release, current_release)

    def digest(self) -> str:
        return content_digest([point.digest() for point in self.points()])
