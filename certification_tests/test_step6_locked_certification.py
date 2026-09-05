from __future__ import annotations

import json
from pathlib import Path

from validation.reasoning_certification import (
    build_evidence_envelope,
    run_locked_certification,
)

CORPUS_PATH = Path("data/quality/reasoning_gold_v2.json")
REVIEW_PATH = Path("docs/quality/reviews/reasoning_gold_v2_review.json")
FREEZE_PATH = Path("data/quality/reasoning_gold_v2.freeze.json")
POLICY_PATH = Path("docs/quality/reasoning_certification_policy_v1.json")
REPORT_PATH = Path("reports/production_validation/step_06.json")
EVIDENCE_PATH = Path("factory/production_validation_evidence/step_06.json")


def test_step6_locked_certification_matches_committed_report_and_evidence() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    validated_sha = str(report["validated_sha"])

    generated = run_locked_certification(
        corpus_path=CORPUS_PATH,
        review_path=REVIEW_PATH,
        freeze_path=FREEZE_PATH,
        policy_path=POLICY_PATH,
        validated_sha=validated_sha,
    )

    assert generated == report
    assert report["locked_evaluation_executed"] is True
    assert report["locked_evaluation_used_for_tuning"] is False
    assert report["authorization"]["locked_use"] == "certification_only"
    assert "independent human review" not in report["authorization"][
        "authorization_reason"
    ]

    canonical_envelope = build_evidence_envelope(
        report_path=REPORT_PATH,
        validated_sha=validated_sha,
    )
    for key, value in canonical_envelope.items():
        assert evidence[key] == value

    assert evidence["certification_mode"] == "solo_maintainer"
    assert evidence["independent_external_review"] == "NOT_PERFORMED"
    assert evidence["historical_locked_result_preexisted"] is True
    assert evidence["locked_evaluation_use"] == "certification_only"
