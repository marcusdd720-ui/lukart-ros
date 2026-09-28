from core.night_shift.autonomy_metrics import AutonomyMetrics


def test_signing_friction_metric() -> None:
    m = AutonomyMetrics(
        attempted=4, closed=2, human_signing_events=1, human_interventions=1, elapsed_seconds=3600
    )
    assert m.closure_rate == 0.5
    assert m.signing_friction == 0.5
