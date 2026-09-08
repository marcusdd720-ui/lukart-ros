from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.lrd_replay_closure_v1 import (
    REQUIRED_LRD_TRUST_CRITICAL_ITEMS,
    ReplayClosureCoverageError,
    ReplayClosureCoverageMatrixV1,
    load_replay_closure_coverage_matrix,
)

MATRIX_PATH = Path("evidence/lrd_01a/replay_closure_coverage_v1.json")


def _raw_matrix() -> dict[str, object]:
    decoded: object = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(decoded, dict)
    return decoded


def test_phase_zero_matrix_classifies_all_trust_critical_dependencies() -> None:
    matrix = load_replay_closure_coverage_matrix(MATRIX_PATH)

    assert matrix.baseline_main_sha == "a884073591295af106baf1d6d87cf178830db315"
    assert matrix.coverage_percentage == 100
    assert matrix.design_gate_pass
    assert len(matrix.items) == len(REQUIRED_LRD_TRUST_CRITICAL_ITEMS) == 30
    assert matrix.matrix_identity.startswith("sha256:")


def test_design_gate_does_not_hide_measured_long_range_gaps() -> None:
    matrix = load_replay_closure_coverage_matrix(MATRIX_PATH)

    assert "artifact_escrow_backend" in matrix.gap_item_ids
    assert "exact_external_responses" in matrix.exact_replay_gap_item_ids
    assert "python_runtime_environment" in matrix.exact_replay_gap_item_ids
    assert "renderer_identity" in matrix.gap_item_ids
    assert matrix.design_gate_pass


def test_missing_trust_critical_item_fails_closed() -> None:
    raw = _raw_matrix()
    items = raw["items"]
    assert isinstance(items, list)
    raw["items"] = items[1:]

    with pytest.raises(ReplayClosureCoverageError, match="coverage is incomplete"):
        ReplayClosureCoverageMatrixV1.from_dict(raw)


def test_unknown_classification_fails_closed() -> None:
    raw = _raw_matrix()
    items = raw["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first["classifications"] = ["MAGIC"]

    with pytest.raises(ReplayClosureCoverageError, match="unknown replay coverage enum"):
        ReplayClosureCoverageMatrixV1.from_dict(raw)


def test_unknown_matrix_field_fails_closed() -> None:
    raw = _raw_matrix()
    raw["implicit_fallback"] = True

    with pytest.raises(ReplayClosureCoverageError, match="unknown=implicit_fallback"):
        ReplayClosureCoverageMatrixV1.from_dict(raw)


def test_noncanonical_item_order_fails_closed() -> None:
    raw = _raw_matrix()
    items = raw["items"]
    assert isinstance(items, list)
    items[0], items[1] = items[1], items[0]

    with pytest.raises(ReplayClosureCoverageError, match="unique and sorted"):
        ReplayClosureCoverageMatrixV1.from_dict(raw)


def test_invalid_baseline_sha_fails_closed() -> None:
    raw = _raw_matrix()
    raw["baseline_main_sha"] = "main"

    with pytest.raises(ReplayClosureCoverageError, match="lowercase full SHA"):
        ReplayClosureCoverageMatrixV1.from_dict(raw)


def test_material_matrix_change_changes_content_identity() -> None:
    baseline = load_replay_closure_coverage_matrix(MATRIX_PATH)
    raw = _raw_matrix()
    items = raw["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first["current_state"] = first["current_state"] + " Updated measurement."
    candidate = ReplayClosureCoverageMatrixV1.from_dict(raw)

    assert candidate.matrix_identity != baseline.matrix_identity
    assert candidate.design_gate_pass
