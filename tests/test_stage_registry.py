from factory.stage_registry import STAGES, get_stage, next_stage


def test_stage_registry_is_contiguous_and_ordered() -> None:
    assert [stage.number for stage in STAGES] == list(range(17))
    assert [stage.number for stage in STAGES] == sorted(stage.number for stage in STAGES)


def test_current_stage_has_an_executable_gate() -> None:
    stage = get_stage(5)
    assert stage.implemented is True
    assert stage.gate == "audit"


def test_next_stage_is_contract_hardening() -> None:
    stage = next_stage(5)
    assert stage is not None
    assert stage.number == 6
    assert stage.name == "Contract Hardening"
