"""Measurement framework that collects metrics without deciding their quality."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from knowledge.graph import KnowledgeGraph
from validation.extraction_quality import ExtractionMetrics
from validation.reasoning_kqm import ReasoningKQMMetrics


@dataclass(frozen=True, slots=True)
class MeasurementSnapshot:
    """Immutable, serializable measurement snapshot."""

    metrics: dict[str, float | int]

    def as_dict(self) -> dict[str, dict[str, float | int]]:
        """Return a stable representation suitable for persistence or reporting."""
        return {"metrics": dict(sorted(self.metrics.items()))}


class MeasurementCollector:
    """Collect deterministic measurements from independent metric providers."""

    def from_extraction(self, metrics: ExtractionMetrics) -> MeasurementSnapshot:
        return self._from_dataclass(metrics)

    def from_reasoning(self, metrics: ReasoningKQMMetrics) -> MeasurementSnapshot:
        return self._from_dataclass(metrics)

    def from_graph(self, graph: KnowledgeGraph) -> MeasurementSnapshot:
        statistics = graph.statistics()
        return MeasurementSnapshot(
            {key: statistics[key] for key in sorted(statistics)}
        )

    @staticmethod
    def _from_dataclass(metrics: object) -> MeasurementSnapshot:
        raw: dict[str, Any] = asdict(metrics)  # type: ignore[arg-type]
        measured = {
            key: value
            for key, value in raw.items()
            if isinstance(value, (int, float))
        }
        return MeasurementSnapshot(dict(sorted(measured.items())))
