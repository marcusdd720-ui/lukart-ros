"""P3-09/H8 realistic, deterministic scale measurement and policy certification."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from core.p2.runtime import LruArtifactCache, bounded_parallel_map

from .contracts import P3ContractError, content_digest
from .semantic_graph import SemanticChangeGraph


@dataclass(frozen=True, slots=True)
class ScaleProfile:
    name: str
    evidence_count: int
    graph_nodes: int
    replay_count: int
    concurrency: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise P3ContractError("scale profile name is required")
        values = (
            self.evidence_count,
            self.graph_nodes,
            self.replay_count,
            self.concurrency,
        )
        if min(values) < 1:
            raise P3ContractError("scale profile values must be positive")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "evidence_count": self.evidence_count,
            "graph_nodes": self.graph_nodes,
            "replay_count": self.replay_count,
            "concurrency": self.concurrency,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class StructuralScaleBudget:
    """Deterministic resource envelope independent from runner wall-clock variance."""

    max_evidence_count: int
    max_graph_nodes: int
    max_replay_count: int
    max_concurrency: int
    max_blast_radius_size: int
    schema: str = "lukart.structural-scale-budget.v1"

    def __post_init__(self) -> None:
        values = (
            self.max_evidence_count,
            self.max_graph_nodes,
            self.max_replay_count,
            self.max_concurrency,
            self.max_blast_radius_size,
        )
        if min(values) < 1:
            raise P3ContractError("structural scale budgets must be positive")
        if self.schema != "lukart.structural-scale-budget.v1":
            raise P3ContractError(f"unsupported structural scale budget schema: {self.schema}")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "max_evidence_count": self.max_evidence_count,
            "max_graph_nodes": self.max_graph_nodes,
            "max_replay_count": self.max_replay_count,
            "max_concurrency": self.max_concurrency,
            "max_blast_radius_size": self.max_blast_radius_size,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class StructuralScaleCertification:
    passed: bool
    failures: tuple[str, ...]
    profile_digest: str
    budget_digest: str


def certify_profile_structure(
    profile: ScaleProfile,
    budget: StructuralScaleBudget,
    *,
    blast_radius_size: int | None = None,
) -> StructuralScaleCertification:
    failures: list[str] = []
    if profile.evidence_count > budget.max_evidence_count:
        failures.append("evidence_count")
    if profile.graph_nodes > budget.max_graph_nodes:
        failures.append("graph_nodes")
    if profile.replay_count > budget.max_replay_count:
        failures.append("replay_count")
    if profile.concurrency > budget.max_concurrency:
        failures.append("concurrency")
    expected_blast_radius = profile.graph_nodes + 1
    observed_blast_radius = (
        expected_blast_radius if blast_radius_size is None else blast_radius_size
    )
    if observed_blast_radius != expected_blast_radius:
        failures.append("blast_radius_identity")
    if observed_blast_radius > budget.max_blast_radius_size:
        failures.append("blast_radius_budget")
    return StructuralScaleCertification(
        passed=not failures,
        failures=tuple(failures),
        profile_digest=profile.digest(),
        budget_digest=budget.digest(),
    )


@dataclass(frozen=True, slots=True)
class SyntheticScaleCase:
    case_id: str
    evidence: tuple[Mapping[str, object], ...]
    graph_dependencies: Mapping[str, tuple[str, ...]]

    def digest(self) -> str:
        return content_digest(
            {
                "case_id": self.case_id,
                "evidence": self.evidence,
                "graph_dependencies": self.graph_dependencies,
            }
        )


def build_synthetic_scale_case(profile: ScaleProfile) -> SyntheticScaleCase:
    evidence = tuple(
        {
            "evidence_id": f"EV-{index:06d}",
            "synthetic": True,
            "content": f"synthetic-evidence-{index}",
        }
        for index in range(profile.evidence_count)
    )
    dependencies: dict[str, tuple[str, ...]] = {}
    for index in range(profile.graph_nodes):
        node_id = f"N-{index:06d}"
        if index == 0:
            dependencies[node_id] = ("EV-000000",)
        else:
            dependencies[node_id] = (f"N-{index - 1:06d}",)
    return SyntheticScaleCase(
        case_id=f"SCALE-{profile.name.upper()}",
        evidence=evidence,
        graph_dependencies=dependencies,
    )


@dataclass(frozen=True, slots=True)
class ScaleMeasurement:
    profile: str
    duration_seconds: float
    peak_memory_bytes: int
    work_digest: str
    cache_hits: int
    cache_misses: int
    blast_radius_size: int

    @property
    def cache_hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total else 0.0


@dataclass(frozen=True, slots=True)
class ScaleBudget:
    max_duration_seconds: float
    max_peak_memory_bytes: int
    min_cache_hit_ratio: float

    def __post_init__(self) -> None:
        if self.max_duration_seconds <= 0 or self.max_peak_memory_bytes < 1:
            raise P3ContractError("scale budgets must be positive")
        if not 0 <= self.min_cache_hit_ratio <= 1:
            raise P3ContractError("cache hit ratio budget must be within 0..1")


@dataclass(frozen=True, slots=True)
class ScaleCertification:
    passed: bool
    failures: tuple[str, ...]
    measurement: ScaleMeasurement


def measure_scale_profile(profile: ScaleProfile) -> ScaleMeasurement:
    """Measure deterministic synthetic work without declaring analytical quality."""

    case = build_synthetic_scale_case(profile)
    cache: LruArtifactCache[str, str] = LruArtifactCache(
        capacity=max(1, min(profile.evidence_count, 1024))
    )
    hits = 0
    misses = 0
    blast_radius_size = 0
    tracemalloc.start()
    started = time.perf_counter()
    try:
        evidence_digests = tuple(content_digest(item) for item in case.evidence)
        for index, evidence_digest in enumerate(evidence_digests):
            key = f"EV-{index:06d}"
            if cache.get(key) is None:
                misses += 1
                cache.put(key, evidence_digest)

        hot_size = min(profile.evidence_count, 512)
        hot_start = profile.evidence_count - hot_size
        for index in range(hot_start, profile.evidence_count):
            if cache.get(f"EV-{index:06d}") is not None:
                hits += 1

        change_graph = SemanticChangeGraph(case.graph_dependencies)
        change_graph.validate_acyclic()
        blast_plan = change_graph.plan(("EV-000000",), materialize_paths=False)
        blast_radius_size = len(blast_plan.affected_ids)
        if blast_radius_size != profile.graph_nodes + 1:
            raise P3ContractError("synthetic blast radius did not traverse full dependency chain")

        case_digest = case.digest()
        replay_inputs: Sequence[int] = tuple(range(profile.replay_count))
        replay_digests = bounded_parallel_map(
            lambda index: content_digest({"case_digest": case_digest, "replay": index}),
            replay_inputs,
            max_workers=profile.concurrency,
        )
        work_digest = content_digest(
            {
                "case": case_digest,
                "evidence": evidence_digests,
                "blast_graph": change_graph.digest(),
                "blast_affected": blast_plan.affected_ids,
                "replays": replay_digests,
            }
        )
    finally:
        duration = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return ScaleMeasurement(
        profile.name,
        duration,
        peak,
        work_digest,
        hits,
        misses,
        blast_radius_size,
    )


def certify_scale(measurement: ScaleMeasurement, budget: ScaleBudget) -> ScaleCertification:
    failures: list[str] = []
    if measurement.duration_seconds > budget.max_duration_seconds:
        failures.append("duration")
    if measurement.peak_memory_bytes > budget.max_peak_memory_bytes:
        failures.append("peak_memory")
    if measurement.cache_hit_ratio < budget.min_cache_hit_ratio:
        failures.append("cache_hit_ratio")
    return ScaleCertification(not failures, tuple(failures), measurement)


def repeated_measurement_digest(
    measure: Callable[[], ScaleMeasurement], *, repetitions: int
) -> tuple[str, ...]:
    if repetitions < 1:
        raise P3ContractError("repetitions must be positive")
    return tuple(measure().work_digest for _ in range(repetitions))
