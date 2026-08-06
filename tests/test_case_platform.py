"""Tests for CaseSpec registry, snapshot schema, validator, stages, multi-case."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.models.case_registry import get_spec, open_case, registered_keys
from knowledge.models.case_snapshot import SCHEMA, CaseSnapshot, build_snapshot_from_workspace
from knowledge.models.snapshot_validator import validate_snapshot


def test_registry_has_both_cases() -> None:
    keys = registered_keys()
    assert "DS_3960_2025" in keys
    assert "II_Kp_459_26" in keys


def test_registry_ds3960_spec() -> None:
    spec = get_spec("DS_3960_2025")
    assert spec.author_name
    assert "Prokuratura" in " ".join(spec.recipient_lines)


def test_registry_ii_kp_spec() -> None:
    spec = get_spec("II_Kp_459_26")
    assert "Mielewczyk" in spec.author_name
    assert "Wejherowo" in " ".join(spec.recipient_lines) or spec.place == "Wejherowo"


def test_open_ds3960_workspace() -> None:
    ws = open_case("DS_3960_2025")
    assert ws.key == "DS_3960_2025"
    assert ws.graph_case_id.startswith("case:")
    assert ws.graph.node_count() >= 1
    assert len(ws.case.facts) >= 1


def test_open_ii_kp_workspace() -> None:
    ws = open_case("II_Kp_459_26")
    assert ws.key == "II_Kp_459_26"
    assert ws.graph_case_id == "case:II_Kp_459_26"
    assert ws.focus_statute_id == "statute:kpk:16"
    assert len(ws.case.facts) >= 1
    assert ws.graph.has_node("statute:kpk:16")


def test_stage_fact_ii_kp() -> None:
    ws = open_case("II_Kp_459_26")
    code = ws.run(stage="FACT")
    assert code == 0
    assert ws.fact_ok is True


def test_stage_law_ds3960() -> None:
    ws = open_case("DS_3960_2025")
    code = ws.run(stage="LAW")
    assert code == 0
    assert ws.law_ok is True


def test_snapshot_schema_and_status() -> None:
    ws = open_case("DS_3960_2025")
    ws.fact_ok = True
    ws.law_ok = True
    ws.review_ok = True
    out = ws.output_dir / "stanowisko_dossier_with_authorities.txt"
    if not out.is_file():
        ws.output_dir.mkdir(parents=True, exist_ok=True)
        out.write_text("dummy dossier for hash\n", encoding="utf-8")

    snap = build_snapshot_from_workspace(ws)
    assert snap.schema == SCHEMA
    data = snap.to_dict()
    assert data["schema"] == SCHEMA
    result = validate_snapshot(data)
    assert result.ok
    assert result.ready_to_publish


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    snap = CaseSnapshot(
        case_key="TEST",
        graph_case_id="case:TEST",
        fact_pass=True,
        law_pass=True,
        review_pass=True,
        workspace_pass=True,
        dossier_path="x.txt",
        dossier_sha256="abc",
    )
    snap.compute_status()
    path = tmp_path / "s.json"
    snap.write(path)
    loaded = CaseSnapshot.load(path)
    assert loaded.schema == SCHEMA
    assert loaded.status == "READY_TO_PUBLISH"
    assert json.loads(path.read_text(encoding="utf-8"))["case_key"] == "TEST"