"""Registry for the post-P7 production validation and certification program."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProgramPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    RELEASE = "RELEASE"


class GateKind(StrEnum):
    EXTERNAL_REVIEW = "external_review"
    IMPLEMENTATION = "implementation"
    MEASUREMENT = "measurement"
    CERTIFICATION = "certification"
    VALIDATION = "validation"
    PRIVACY = "privacy"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class ProgramStep:
    number: int
    name: str
    priority: ProgramPriority
    objective: str
    gate_kind: GateKind


PROGRAM_STEPS: tuple[ProgramStep, ...] = (
    ProgramStep(
        1,
        "Extraction Gold Corpus independent review and freeze",
        ProgramPriority.P0,
        "Freeze a trustworthy extraction benchmark after independent review.",
        GateKind.EXTERNAL_REVIEW,
    ),
    ProgramStep(
        2,
        "ReferenceFactAgent improvement",
        ProgramPriority.P0,
        "Improve precision, recall, F1, and critical recall on development/validation only.",
        GateKind.IMPLEMENTATION,
    ),
    ProgramStep(
        3,
        "Extraction KQM certification attempt",
        ProgramPriority.P0,
        "Measure the candidate extractor and issue a certification decision.",
        GateKind.CERTIFICATION,
    ),
    ProgramStep(
        4,
        "Reasoning Gold Corpus v2",
        ProgramPriority.P0,
        "Build a broader and harder reasoning benchmark candidate.",
        GateKind.IMPLEMENTATION,
    ),
    ProgramStep(
        5,
        "Independent review and freeze Reasoning Corpus",
        ProgramPriority.P0,
        "Independently review and freeze the reasoning benchmark.",
        GateKind.EXTERNAL_REVIEW,
    ),
    ProgramStep(
        6,
        "Reasoning Engine KQM certification",
        ProgramPriority.P0,
        "Measure reasoning correctness, abstention, and contradiction handling.",
        GateKind.CERTIFICATION,
    ),
    ProgramStep(
        7,
        "End-to-End Gold Cases",
        ProgramPriority.P0,
        "Measure the complete product path on versioned Gold Cases.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        8,
        "Agent Certification Program",
        ProgramPriority.P1,
        "Certify controlled agents against explicit capability-specific benchmarks.",
        GateKind.CERTIFICATION,
    ),
    ProgramStep(
        9,
        "Adversarial Gold Cases",
        ProgramPriority.P1,
        "Stress evidence, contradiction, abstention, and adversarial verification behavior.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        10,
        "Case Replay regression suite",
        ProgramPriority.P1,
        "Prove deterministic replay and classify expected versus unexpected drift.",
        GateKind.VALIDATION,
    ),
    ProgramStep(
        11,
        "Change Propagation stress tests",
        ProgramPriority.P1,
        "Validate downstream impact selection and broad fallback behavior.",
        GateKind.VALIDATION,
    ),
    ProgramStep(
        12,
        "Controlled Learning experiments",
        ProgramPriority.P1,
        "Exercise real measured P4-P7 improvement cycles without production mutation.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        13,
        "Model and strategy benchmark and routing",
        ProgramPriority.P2,
        "Benchmark interchangeable strategies and route only on measured capability.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        14,
        "Automatic candidate generation",
        ProgramPriority.P2,
        "Generate bounded improvement candidates without granting deployment authority.",
        GateKind.IMPLEMENTATION,
    ),
    ProgramStep(
        15,
        "Local private-case pilot",
        ProgramPriority.P2,
        "Validate real cases locally without publishing private evidence or PII.",
        GateKind.PRIVACY,
    ),
    ProgramStep(
        16,
        "Renderer and final report quality",
        ProgramPriority.P2,
        "Validate human-facing evidence, timeline, reasoning, and dossier quality.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        17,
        "Performance budgets and SLA",
        ProgramPriority.P3,
        "Measure runtime, model calls, cost units, memory, and declared service budgets.",
        GateKind.MEASUREMENT,
    ),
    ProgramStep(
        18,
        "Security and privacy hardening",
        ProgramPriority.P3,
        "Harden secrets, PII, sandbox, local-data boundaries, and auditability.",
        GateKind.PRIVACY,
    ),
    ProgramStep(
        19,
        "Release versioning and migration policy",
        ProgramPriority.P3,
        "Stabilize versioning and migration contracts for product artifacts.",
        GateKind.RELEASE,
    ),
    ProgramStep(
        20,
        "LUKART v1 Release Candidate",
        ProgramPriority.RELEASE,
        "Issue the release-candidate decision only after all critical gates pass.",
        GateKind.RELEASE,
    ),
)


def get_program_step(number: int) -> ProgramStep:
    for step in PROGRAM_STEPS:
        if step.number == number:
            return step
    raise ValueError(f"unknown production validation step: {number}")


def next_program_step(number: int) -> ProgramStep | None:
    for step in PROGRAM_STEPS:
        if step.number > number:
            return step
    return None
