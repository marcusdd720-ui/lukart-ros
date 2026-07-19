"""
Knowledge Operating System (KOS)

File: knowledge/project_state.py
Version: 1.0
Sprint: F-013
Status: Draft

Represents the current state of the KOS project.
"""

from dataclasses import dataclass, field


@dataclass
class ProjectState:
    """
    Represents the current KOS project state.
    """

    iteration: int
    active_case: str

    validated_patterns: list[str] = field(default_factory=list)
    active_hypotheses: list[str] = field(default_factory=list)
    accepted_adrs: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)