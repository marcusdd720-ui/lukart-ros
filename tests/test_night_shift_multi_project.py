from pathlib import Path

from core.night_shift.contracts import RiskClass
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.multi_project import compile_dispatches
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState
from core.night_shift.project_registry import load_project_registry
from core.night_shift.scheduler import ResourcePolicy


def test_stale_lukart_is_blocked_and_latam_is_selected() -> None:
    registry = load_project_registry(
        Path("docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml")
    )
    executors = load_executor_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml")
    )
    snapshot = PortfolioSnapshot(
        "live",
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
            ProjectState(
                "SYNTH_V071",
                "marcusdd720-ui/synthetic-test-data",
                "e" * 40,
                "SYNTH-V071",
                60,
                RiskClass.R1,
                evidence_refs=("github:main",),
            ),
        ),
    )
    dispatches = compile_dispatches(
        snapshot=snapshot,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(
            technical_active_max=2, local_code_writers_max=1, heavy_local_compute_max=1
        ),
        now_epoch=10,
    )
    assert [x.task_id for x in dispatches] == ["LATAM-I11", "SYNTH-V071"]


def test_blocked_project_does_not_require_executor_capability() -> None:
    from core.night_shift.executor_registry import ExecutorProfile

    registry = load_project_registry(
        Path("docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml")
    )
    executors = (
        ExecutorProfile(
            "change-only",
            ("git", "bounded_code_change"),
            True,
            False,
            1,
            True,
            False,
            False,
            2,
        ),
    )
    snapshot = PortfolioSnapshot(
        "blocked-isolation",
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
    dispatches = compile_dispatches(
        snapshot=snapshot,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(
            technical_active_max=2,
            local_code_writers_max=1,
            heavy_local_compute_max=1,
        ),
        now_epoch=10,
    )
    assert [item.task_id for item in dispatches] == ["LATAM-I11"]
