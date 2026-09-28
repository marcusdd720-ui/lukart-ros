from pathlib import Path

from core.night_shift.contracts import RiskClass
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.night_cycle import run_shadow_cycle
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState
from core.night_shift.project_registry import load_project_registry
from core.night_shift.scheduler import ResourcePolicy


def test_three_project_shadow_e2e_matches_live_state_model() -> None:
    registry = load_project_registry(
        Path("docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml")
    )
    executors = load_executor_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml")
    )
    snap = PortfolioSnapshot(
        "live-2026-09-28",
        1,
        100,
        (
            ProjectState(
                "LUKART_PR313",
                "marcusdd720-ui/lukart-ros",
                "3362bb35c6b5a54fcf51c58077d3bc4aeecbc0be",
                "LUKART-PR313-CLOSE",
                95,
                RiskClass.R3,
                "a684ea0380a061c5062557db7b03704797396c7a",
                "2f81977f64ad7ec550b5dc7a43540a144ac7bc70",
                (),
                ("github:pr313",),
            ),
            ProjectState(
                "LATAM_I11",
                "marcusdd720-ui/Latam-Career-OS",
                "b0680b77c9aa527d50da0a62b2b8c8c12160f9a6",
                "LATAM-I11",
                70,
                RiskClass.R2,
                evidence_refs=("github:main",),
            ),
            ProjectState(
                "SYNTH_V071",
                "marcusdd720-ui/synthetic-test-data",
                "cd157d48f580c9d613cee99ea0ac8acf32162faa",
                "SYNTH-V071",
                60,
                RiskClass.R1,
                evidence_refs=("github:main",),
            ),
        ),
    )
    result = run_shadow_cycle(
        snapshot=snap,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(
            technical_active_max=2, local_code_writers_max=1, heavy_local_compute_max=1
        ),
        now_epoch=10,
    )
    assert result.plan.mutating_actions_executed == 0
    assert tuple(x.task_id for x in result.plan.dispatches) == (
        "LATAM-I11",
        "SYNTH-V071",
    )
    assert result.report.blocked == ("LUKART-PR313-CLOSE",)
