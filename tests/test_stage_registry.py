from pathlib import Path

from factory.stage_registry import STAGES, get_stage, next_stage


def test_stage_registry_is_contiguous_and_ordered() -> None:
    assert [stage.number for stage in STAGES] == list(range(17))
    assert [stage.number for stage in STAGES] == sorted(stage.number for stage in STAGES)


def test_current_stage_has_an_executable_gate() -> None:
    stage = get_stage(6)
    assert stage.implemented is True
    assert stage.gate == "contract"


def test_next_stage_is_fact_identity_and_deduplication() -> None:
    stage = next_stage(6)
    assert stage is not None
    assert stage.number == 7
    assert stage.name == "Fact Identity and Deduplication"


def test_stage_gate_workflow_exposes_read_only_required_pr_check() -> None:
    workflow = Path(".github/workflows/stage-gate.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert "gate:" in workflow
    assert "contents: read" in workflow
    assert 'EVENT_NAME: ${{ github.event_name }}' in workflow
    assert 'echo "stage=0" >> "${GITHUB_OUTPUT}"' in workflow
    assert 'steps.stage.outputs.stage' in workflow
