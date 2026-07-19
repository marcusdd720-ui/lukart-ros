"""
Knowledge Operating System (KOS)

File: knowledge/project_loader.py
Version: 1.0
Sprint: F-013

Loads and saves the current KOS project state.
"""

from pathlib import Path

import yaml

from knowledge.project_state import ProjectState


class ProjectStateLoader:
    """
    Loads the current project state stored in project_state.yaml.
    """

    def __init__(self, path: str = "knowledge/project_state.yaml"):
        self.path = Path(path)

    def load(self) -> ProjectState:

        if not self.path.exists():
            raise FileNotFoundError(
                f"Project state file not found: {self.path}"
            )

        with open(self.path, encoding="utf-8") as file:
            data = yaml.safe_load(file)

        return ProjectState(**data)