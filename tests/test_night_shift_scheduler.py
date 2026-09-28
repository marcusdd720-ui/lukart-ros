import pytest

from core.night_shift.contracts import NightShiftContractError, RiskClass
from core.night_shift.scheduler import ResourcePolicy, WorkItem, compile_ready_queue, select_batch


def test_queue_is_deterministic_and_closure_first_within_priority() -> None:
    items = (
        WorkItem("b", 1, 60, True, (), RiskClass.R1),
        WorkItem("a", 1, 90, True, (), RiskClass.R1),
        WorkItem("blocked", 0, 99, True, ("root",), RiskClass.R0),
    )
    assert [item.task_id for item in compile_ready_queue(items)] == ["a", "b"]


def test_resource_governor_limits_writer_and_heavy_work() -> None:
    items = (
        WorkItem("heavy-a", 0, 80, True, (), RiskClass.R1, True, True),
        WorkItem("writer-b", 1, 70, True, (), RiskClass.R1, True, False),
        WorkItem("light-c", 2, 60, True, (), RiskClass.R0, False, False),
    )
    selected = select_batch(
        items,
        policy=ResourcePolicy(
            technical_active_max=2,
            local_code_writers_max=1,
            heavy_local_compute_max=1,
        ),
    )
    assert [item.task_id for item in selected] == ["heavy-a", "light-c"]


def test_invalid_closure_percent_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="closure_percent"):
        WorkItem("bad", 1, 101, True, (), RiskClass.R0)


def test_invalid_resource_policy_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="technical_active_max"):
        ResourcePolicy(technical_active_max=0)


def test_executor_parallel_capacity_is_enforced() -> None:
    items = (
        WorkItem("a", 0, 90, True, (), RiskClass.R1, False, False, "cloud", 2),
        WorkItem("b", 1, 80, True, (), RiskClass.R1, False, False, "cloud", 2),
        WorkItem("c", 2, 70, True, (), RiskClass.R1, False, False, "cloud", 2),
    )
    selected = select_batch(
        items,
        policy=ResourcePolicy(
            technical_active_max=3,
            local_code_writers_max=1,
            heavy_local_compute_max=1,
        ),
    )
    assert [item.task_id for item in selected] == ["a", "b"]
