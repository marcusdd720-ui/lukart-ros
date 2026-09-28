from pathlib import Path

from core.night_shift.runtime_profiles import (
    RuntimeEvidence,
    RuntimeRequirements,
    load_runtime_profiles,
)


def test_runtime_matrix_loads_and_local_runtime_is_validated() -> None:
    path = Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    profiles = load_runtime_profiles(path)
    local = [x for x in profiles if x.runtime_id == "local_journal"][0]
    assert local.evidence is RuntimeEvidence.VALIDATED
    assert local.satisfies(RuntimeRequirements(crash_resume=True, idempotent_steps=True))


def test_temporal_satisfies_distributed_requirement_but_is_not_validated() -> None:
    profiles = load_runtime_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    )
    temporal = [x for x in profiles if x.runtime_id == "temporal"][0]
    assert temporal.distributed_workers
    assert temporal.evidence is RuntimeEvidence.DOCUMENTED
