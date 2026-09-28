from core.night_shift.executor_registry import ExecutorProfile
from core.night_shift.routing import route_executor


def test_router_picks_cheapest_capable_executor() -> None:
    executors = (
        ExecutorProfile("expensive", ("git", "bounded_code_change"), True, False, 5, True),
        ExecutorProfile("cheap", ("git", "bounded_code_change"), True, False, 1, True),
    )
    decision = route_executor(
        required_capabilities=("git", "bounded_code_change"), executors=executors, mutating=True
    )
    assert decision.executor_id == "cheap"
    assert decision.requires_local_writer is False
    assert decision.heavy_compute is False
