from pathlib import Path

from core.night_shift.contracts import RiskClass
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState
from core.night_shift.project_registry import load_project_registry
from core.night_shift.scheduler import ResourcePolicy
from core.night_shift.shadow_runner import plan_shadow


def test_shadow_plan_never_executes_mutation() -> None:
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
                "LATAM_I11",
                "marcusdd720-ui/Latam-Career-OS",
                "a" * 40,
                "LATAM-I11",
                70,
                RiskClass.R2,
                evidence_refs=("github:main",),
            ),
        ),
    )
    plan = plan_shadow(
        snapshot=snap,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(),
        now_epoch=10,
    )
    assert plan.mutating_actions_executed == 0
    assert plan.dispatches[0].task_id == "LATAM-I11"


def test_shadow_digest_binds_policy_and_planning_time() -> None:
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
                "LATAM_I11",
                "marcusdd720-ui/Latam-Career-OS",
                "a" * 40,
                "LATAM-I11",
                70,
                RiskClass.R2,
                evidence_refs=("github:main",),
            ),
        ),
    )
    first = plan_shadow(
        snapshot=snap,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(),
        now_epoch=10,
    )
    second = plan_shadow(
        snapshot=snap,
        registry=registry,
        executors=executors,
        resource_policy=ResourcePolicy(technical_active_max=3),
        now_epoch=11,
    )
    assert first.digest() != second.digest()
    assert first.project_registry_digest == registry.digest()
