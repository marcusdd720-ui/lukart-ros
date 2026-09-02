"""Lifecycle registry for automated LukArt ROS stage gates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Stage:
    number: int
    name: str
    gate: str
    implemented: bool


STAGES: tuple[Stage, ...] = (
    Stage(0, "Factory / CI", "quality", True),
    Stage(1, "KQM", "kqm", True),
    Stage(2, "Fact Extraction", "extraction", True),
    Stage(3, "Fact Projection", "projection", True),
    Stage(4, "End-to-End", "e2e", True),
    Stage(5, "Audit and Stabilization", "audit", True),
    Stage(6, "Contract Hardening", "contract", True),
    Stage(7, "Fact Identity and Deduplication", "dedup", False),
    Stage(8, "Relation Layer", "relations", False),
    Stage(9, "Validation 2.0", "validation", False),
    Stage(10, "Measurement Framework", "measurement", False),
    Stage(11, "Independent Evaluation", "independent-evaluation", False),
    Stage(12, "Production Extraction Contract", "production-contract", False),
    Stage(13, "Production Pipeline", "production-pipeline", False),
    Stage(14, "Benchmark Expansion", "benchmark", False),
    Stage(15, "Self-Healing and Change Propagation", "self-healing", False),
    Stage(16, "MVROS v1", "release", False),
)


def get_stage(number: int) -> Stage:
    for stage in STAGES:
        if stage.number == number:
            return stage
    raise ValueError(f"unknown stage: {number}")


def next_stage(number: int) -> Stage | None:
    for stage in STAGES:
        if stage.number > number:
            return stage
    return None
