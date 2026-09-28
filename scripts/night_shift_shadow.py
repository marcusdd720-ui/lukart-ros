#!/usr/bin/env python
"""Run a read-only Night Shift shadow cycle from live Git refs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.live_observer import observe_portfolio
from core.night_shift.night_cycle import run_shadow_cycle
from core.night_shift.project_registry import load_project_registry
from core.night_shift.scheduler import ResourcePolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-inputs",
        default="docs/execution_profiles/NIGHT_SHIFT_LIVE_INPUTS_V1.yaml",
    )
    parser.add_argument(
        "--project-registry",
        default="docs/execution_profiles/NIGHT_SHIFT_PROJECT_REGISTRY_V1.yaml",
    )
    parser.add_argument(
        "--executor-registry",
        default="docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml",
    )
    parser.add_argument("--output", default="reports/night_shift_shadow_latest.json")
    parser.add_argument("--now-epoch", type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    now_epoch = int(time()) if args.now_epoch is None else args.now_epoch
    snapshot = observe_portfolio(args.live_inputs, now_epoch=now_epoch)
    result = run_shadow_cycle(
        snapshot=snapshot,
        registry=load_project_registry(args.project_registry),
        executors=load_executor_profiles(args.executor_registry),
        resource_policy=ResourcePolicy(
            technical_active_max=2,
            local_code_writers_max=1,
            heavy_local_compute_max=1,
        ),
        now_epoch=now_epoch,
    )
    payload = {
        "mode": "SHADOW",
        "snapshot_id": snapshot.snapshot_id,
        "observed_at_epoch": snapshot.observed_at_epoch,
        "expires_at_epoch": snapshot.expires_at_epoch,
        "portfolio_digest": result.plan.portfolio_digest,
        "plan_digest": result.plan.digest(),
        "mutating_actions_executed": result.plan.mutating_actions_executed,
        "dispatches": [
            {
                "project_id": item.project_id,
                "task_id": item.task_id,
                "executor_id": item.executor_id,
                "repository": item.repository,
            }
            for item in result.plan.dispatches
        ],
        "blocked": list(result.report.blocked),
        "planned": list(result.report.planned),
        "evidence_refs": list(result.report.evidence_refs),
        "projects": [
            {
                "project_id": item.project_id,
                "repository": item.repository,
                "main_sha": item.main_sha,
                "candidate_sha": item.candidate_sha,
                "candidate_base_sha": item.candidate_base_sha,
                "candidate_stale": item.candidate_stale,
                "ready": item.ready,
            }
            for item in snapshot.projects
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
