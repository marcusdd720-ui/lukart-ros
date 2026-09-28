from pathlib import Path

from core.night_shift.contracts import RiskClass
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.night_cycle import run_shadow_cycle
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState
from core.night_shift.project_registry import load_project_registry
from core.night_shift.scheduler import ResourcePolicy


def test_shadow_cycle_reports_blocked_and_planned() -> None:
    registry = load_project_registry(
        Path("docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml")
    )
    executors = load_executor_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml")
    )
    snap = PortfolioSnapshot(
        "s",
        1,
        100,
        (
            ProjectState(
                "LUKART_PR313",
                "marcusdd720-ui/lukart-ros",
                "a" * 40,
                "LUKART-PR313-CLOSE",
                95,
                RiskClass.R3,
                "b" * 40,
                "c" * 40,
                (),
                ("github:pr313",),
            ),
            ProjectState(
                "LATAM_I11",
                "marcusdd720-ui/Latam-Career-OS",
                "d" * 40,
                "LATAM-I11",
                70,
                RiskClass.R2,
                evidence_refs=("github:main",),
            ),
        ),
    )
    result = run_shadow_cycle(
        snapshot=snap,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(),
        now_epoch=10,
    )
    assert "LUKART-PR313-CLOSE" in result.report.blocked
    assert "LATAM-I11" in result.report.planned
