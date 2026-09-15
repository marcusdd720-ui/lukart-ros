from __future__ import annotations

import json
from pathlib import Path

from core.case_ledger.contracts import CaseId
from core.case_ledger.ledger import CanonicalCaseLedger
from core.p3.contracts import RuntimeIdentity

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "case_testy" / "synthetic_case.json"


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="1" * 40,
        schema_version="synthetic-case-testy-golden-v1",
        config_digest="2" * 64,
        corpus_digest="3" * 64,
    )


def test_synthetic_golden_case_is_content_addressed_and_replayable(tmp_path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["synthetic"] is True
    assert fixture["expected"]["statement_recorded"] is True
    assert fixture["expected"]["content_classification"] == "CLAIM"

    case_id = CaseId(fixture["case_id"])
    payload = {
        "statement": fixture["statement"],
        "content_classification": fixture["expected"]["content_classification"],
        "synthetic": True,
    }

    with CanonicalCaseLedger(tmp_path / "golden.db") as ledger:
        event = ledger.append_event(
            case_id=case_id,
            event_type="synthetic.user-statement.v1",
            runtime_identity=_runtime(),
            payload=payload,
            expected_head=None,
        )
        exported = ledger.export_case(case_id)

    verified = CanonicalCaseLedger.verify_export(exported.canonical_dict())
    assert verified == exported
    assert verified.events == (event,)
    assert verified.events[0].payload["content_classification"] == "CLAIM"
