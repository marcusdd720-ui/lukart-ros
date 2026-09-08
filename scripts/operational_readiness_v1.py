"""Execute the OPR-01 exact-SHA operational-readiness drill."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from core.enterprise.operational_readiness_v1 import (
    ReadinessOutcome,
    run_operational_readiness_drill,
)
from core.p3.contracts import canonical_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic OPR-01 operational readiness")
    parser.add_argument("--code-sha", default=os.environ.get("CANDIDATE_SHA", ""))
    parser.add_argument("--expected-code-sha", default=os.environ.get("CANDIDATE_SHA", ""))
    parser.add_argument("--runbook", default="docs/POST_V1_OPERATIONS.md")
    parser.add_argument("--output")
    args = parser.parse_args()

    runbook_path = Path(args.runbook)
    if not runbook_path.is_file():
        parser.error(f"runbook does not exist: {runbook_path}")
    if not args.code_sha or not args.expected_code_sha:
        parser.error("--code-sha and --expected-code-sha (or CANDIDATE_SHA) are required")

    with tempfile.TemporaryDirectory(prefix="opr01-") as directory:
        report = run_operational_readiness_drill(
            code_sha=args.code_sha,
            expected_code_sha=args.expected_code_sha,
            workspace=Path(directory),
            runbook_text=runbook_path.read_text(encoding="utf-8"),
        )
    report.verify()
    serialized = canonical_json(report.canonical_dict()) + "\n"

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
    else:
        print(json.dumps(report.canonical_dict(), indent=2, sort_keys=True))

    print(f"OPR01_EXACT_SHA={report.code_sha}")
    print(f"OPR01_REPORT_DIGEST={report.report_digest}")
    print(f"OPR01_OUTCOME={report.outcome.value}")
    return 0 if report.outcome is ReadinessOutcome.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
