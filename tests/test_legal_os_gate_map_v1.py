"""Contract tests for the static LUKART LEGAL OS gate prerequisites."""
import pytest

from core.operations.legal_os_gate_map_v1 import (
    all_ros_gates,
    can_promote_from_mapping_only,
    map_ros_gate,
)


def test_canonical_gate_set_and_work_prerequisites():
    assert all_ros_gates() == (
        "G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G7.5", "G8"
    )
    work = {f"HG-{i:02d}" for i in range(1, 10)}
    observed = set()
    for gate in all_ros_gates():
        requirements = map_ros_gate(gate)
        assert requirements.ros_gate == gate
        assert requirements.admission == "NOT_ADMITTED"
        assert requirements.ros_only_requirements
        assert set(requirements.work_prerequisites) <= work
        observed.update(requirements.work_prerequisites)
    assert observed == work


@pytest.mark.parametrize("gate", ["", "G9", "HG-09", "G7.6", None, 42])
def test_unknown_gate_is_rejected(gate):
    with pytest.raises(ValueError, match="LEGAL_OS_UNKNOWN_ROS_GATE"):
        map_ros_gate(gate)


def test_finish_requires_distinct_artifact_integrity():
    finish = map_ros_gate("G7.5")
    assert "HG-09" in finish.work_prerequisites
    assert "finish_pass_exact_artifact" in finish.ros_only_requirements
    assert "docx_pdf_exact_byte_hashes" in finish.ros_only_requirements
    assert "invalidate_finish_on_any_byte_change" in finish.ros_only_requirements
    assert not can_promote_from_mapping_only()


def test_external_action_requires_independent_checks():
    gate = map_ros_gate("G8")
    assert "independent_exact_sha_product_admission" in gate.ros_only_requirements
    assert "native_work_release_receipt" in gate.ros_only_requirements
    assert "separate_human_send_or_filing_authority" in gate.ros_only_requirements
    assert gate.admission == "NOT_ADMITTED"
