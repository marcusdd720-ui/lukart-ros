from __future__ import annotations

import json
from pathlib import Path

from factory.quality.test_profiles import (
    ProfileName,
    ProfileStatus,
    StepResult,
    StepStatus,
    TestProfile,
    TestStep,
    run_profile,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "case_test_report.schema.json"
PR_WORKFLOW = ROOT / ".github" / "workflows" / "case-testy-pr-gate.yml"
SHA = "a" * 40


def _semantic_payload(result) -> dict[str, object]:
    payload = result.to_dict()
    payload.pop("started_at")
    payload.pop("ended_at")
    return payload


def test_profile_rerun_is_semantically_deterministic_for_same_sha_and_results() -> None:
    step = TestStep("deterministic", ("python", "-V"))
    profile = TestProfile(
        name=ProfileName.FAST,
        steps=(step,),
        required_step_names=(step.name,),
    )

    def executor(item: TestStep) -> StepResult:
        return StepResult(
            name=item.name,
            command=item.command,
            required=item.required,
            status=StepStatus.PASS,
            exit_code=0,
            reason="synthetic deterministic PASS",
        )

    first = run_profile(profile, SHA, executor=executor, checkout_sha=SHA)
    second = run_profile(profile, SHA, executor=executor, checkout_sha=SHA)

    assert first.status is ProfileStatus.PASS
    assert second.status is ProfileStatus.PASS
    assert _semantic_payload(first) == _semantic_payload(second)


def test_external_report_schema_tracks_fail_closed_report_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert schema["properties"]["schema_version"]["const"] == "lukart.case-test-profile-report.v1"
    assert required == {
        "schema_version",
        "repository",
        "ref",
        "git_sha",
        "checkout_sha",
        "profile",
        "started_at",
        "ended_at",
        "required_steps",
        "steps",
        "status",
        "reason",
    }
    assert schema["properties"]["git_sha"]["pattern"] == "^[0-9a-fA-F]{40}$"
    assert schema["properties"]["checkout_sha"]["pattern"] == "^[0-9a-fA-F]{40}$"
    assert set(schema["properties"]["profile"]["enum"]) == {item.value for item in ProfileName}
    assert set(schema["properties"]["status"]["enum"]) == {item.value for item in ProfileStatus}
    assert set(schema["properties"]["steps"]["items"]["properties"]["status"]["enum"]) == {
        item.value for item in StepStatus
    }


def test_pr_workflow_preserves_failure_evidence_fail_closed() -> None:
    text = PR_WORKFLOW.read_text(encoding="utf-8")
    assert "Validate required reports" in text
    assert "if: always()" in text
    assert "Upload CASE-TESTY evidence" in text
    assert "if-no-files-found: error" in text
    assert "case-testy-pr-${{ github.event.pull_request.head.sha }}" in text
