from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_benchmark import RuntimeObservation, select_runtime
from core.night_shift.runtime_profiles import RuntimeRequirements, load_runtime_profiles


def test_only_validated_runtime_can_win() -> None:
    profiles = load_runtime_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    )
    local = [x for x in profiles if x.runtime_id == "local_journal"][0]
    obs = RuntimeObservation(
        local.digest(), True, True, False, False, False, 10, 5, ("test:restart",)
    )
    decision = select_runtime(
        profiles=profiles, observations=(obs,), requirements=RuntimeRequirements()
    )
    assert decision.runtime_id == "local_journal"


def test_no_observation_fails_closed() -> None:
    profiles = load_runtime_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    )
    with pytest.raises(NightShiftContractError, match="no validated runtime"):
        select_runtime(profiles=profiles, observations=(), requirements=RuntimeRequirements())


def test_runtime_decision_binds_requirements_digest() -> None:
    profiles = load_runtime_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    )
    local = [x for x in profiles if x.runtime_id == "local_journal"][0]
    requirements = RuntimeRequirements(crash_resume=True, idempotent_steps=True)
    obs = RuntimeObservation(
        local.digest(), True, True, False, False, False, 10, 5, ("test:restart",)
    )
    decision = select_runtime(
        profiles=profiles,
        observations=(obs,),
        requirements=requirements,
    )
    assert decision.requirements_digest == requirements.digest()


def test_distributed_requirement_requires_observed_pass() -> None:
    profiles = load_runtime_profiles(
        Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
    )
    temporal = [x for x in profiles if x.runtime_id == "temporal"][0]
    validated = replace(temporal, evidence=temporal.evidence.VALIDATED)
    observation = RuntimeObservation(
        validated.digest(), True, True, True, True, False, 10, 5, ("test:distributed",)
    )
    with pytest.raises(NightShiftContractError, match="no validated runtime"):
        select_runtime(
            profiles=(validated,),
            observations=(observation,),
            requirements=RuntimeRequirements(distributed_workers=True),
        )
