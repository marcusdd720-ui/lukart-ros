from knowledge.pipeline_result import PipelineResult, PipelineStatus


def test_pipeline_result_success_is_auditable():
    result = PipelineResult(
        status=PipelineStatus.SUCCESS,
        stage_results={"build": "passed", "validation": "passed"},
    )

    assert result.ok is True
    assert result.has_output is False
    assert result.errors == []


def test_pipeline_result_partial_preserves_warnings_and_output_state():
    result = PipelineResult(status=PipelineStatus.PARTIAL)
    result.add_warning("extractor returned no entities")
    result.add_error("validation found an orphan node")

    assert result.ok is False
    assert result.warnings == ["extractor returned no entities"]
    assert result.errors == ["validation found an orphan node"]
