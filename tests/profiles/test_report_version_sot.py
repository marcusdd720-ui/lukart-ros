from factory.quality.report_schema import REPORT_SCHEMA
from factory.quality.test_profiles import (
    ProfileName,
    StepResult,
    StepStatus,
    TestProfile,
    TestStep,
    run_profile,
)

SHA = "69f4843be7fc94c446f72b891a8fb44fbf9d9ed3"


def test_generated_report_uses_canonical_schema_version() -> None:
    step = TestStep("version-sot", ("python", "-V"))
    profile = TestProfile(
        name=ProfileName.FAST,
        steps=(step,),
        required_step_names=(step.name,),
    )

    result = run_profile(
        profile,
        SHA,
        executor=lambda item: StepResult(
            name=item.name,
            command=item.command,
            required=item.required,
            status=StepStatus.PASS,
            exit_code=0,
            reason="synthetic pass",
        ),
    )

    assert result.schema_version == REPORT_SCHEMA
    assert result.to_dict()["schema_version"] == REPORT_SCHEMA
