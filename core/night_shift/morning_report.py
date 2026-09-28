"""Deterministic morning report for unattended/shadow execution."""

from __future__ import annotations

from dataclasses import dataclass

from .shadow_runner import ShadowPlan


@dataclass(frozen=True, slots=True)
class MorningReport:
    closed: tuple[str, ...]
    ready_for_human: tuple[str, ...]
    blocked: tuple[str, ...]
    planned: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def build_shadow_report(
    *, plan: ShadowPlan, blocked: tuple[str, ...], evidence_refs: tuple[str, ...]
) -> MorningReport:
    planned = tuple(sorted(x.task_id for x in plan.dispatches))
    return MorningReport((), (), tuple(sorted(blocked)), planned, tuple(sorted(evidence_refs)))
