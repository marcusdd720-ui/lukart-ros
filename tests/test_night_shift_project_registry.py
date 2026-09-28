from pathlib import Path

from core.night_shift.project_registry import load_project_registry


def test_project_registry_loads_three_projects() -> None:
    registry = load_project_registry(
        Path("docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml")
    )
    assert len(registry.projects) == 3
    assert registry.by_project_id("LATAM_I11").repository == "marcusdd720-ui/Latam-Career-OS"
