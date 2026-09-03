"""Evidence-readiness gate for declared case requirements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    name: str
    relative_path: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class EvidenceReadiness:
    ready: bool
    missing: tuple[str, ...]


def check_evidence_readiness(
    case_root: Path,
    requirements: list[EvidenceRequirement],
) -> EvidenceReadiness:
    root = case_root.expanduser().resolve()
    missing: list[str] = []
    for requirement in requirements:
        candidate = (root / requirement.relative_path).resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"Evidence path escapes case root: {requirement.relative_path}")
        if requirement.required and not candidate.is_file():
            missing.append(requirement.name)
    return EvidenceReadiness(ready=not missing, missing=tuple(sorted(missing)))


def require_evidence_readiness(
    case_root: Path,
    requirements: list[EvidenceRequirement],
) -> None:
    result = check_evidence_readiness(case_root, requirements)
    if not result.ready:
        raise ValueError("Missing required evidence: " + ", ".join(result.missing))
