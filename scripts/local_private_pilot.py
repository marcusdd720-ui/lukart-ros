"""Execute Step 15 against a real Case while keeping all Case data local."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.local_case_store import validate_data_root
from knowledge.models.case_registry import get_spec
from knowledge.models.case_workspace import STAGES
from validation.local_private_pilot import (
    attest_local_private_pilot,
    write_local_pilot_attestation,
)


def _current_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _case_fingerprint(case_key: str) -> str:
    return hashlib.sha256(case_key.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a real private Case locally and record a privacy-safe Step 15 attestation"
    )
    parser.add_argument("--case", required=True, help="Private local Case key")
    parser.add_argument(
        "--data-root",
        required=True,
        help="Private MVROS data root outside the Git repository",
    )
    parser.add_argument(
        "--stage",
        default=None,
        choices=STAGES,
        help="Optional single stage; omit to run the normal full Case pipeline",
    )
    args = parser.parse_args()

    data_root = validate_data_root(Path(args.data_root), repo_root=ROOT)
    spec = get_spec(args.case, data_root=data_root)
    workspace = spec.open(data_root=data_root)
    kwargs = spec.run_kwargs()
    if args.stage:
        kwargs["stage"] = args.stage

    validated_sha = _current_sha()
    exit_code = workspace.run(**kwargs)
    completed_stages = 0 if exit_code != 0 else (1 if args.stage else len(STAGES))

    result_dir = data_root / "pilot-results"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{_case_fingerprint(args.case)}.json"
    result_path.write_text(
        json.dumps(
            {
                "case_fingerprint": _case_fingerprint(args.case),
                "pipeline_exit_code": exit_code,
                "stages_completed": completed_stages,
                "validated_sha": validated_sha,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    attestation = attest_local_private_pilot(
        case_key=args.case,
        data_root=data_root,
        repo_root=ROOT,
        validated_sha=validated_sha,
        result_path=result_path,
        pipeline_exit_code=exit_code,
        stages_executed=completed_stages,
        pii_committed=False,
        private_evidence_committed=False,
    )
    attestation_path = write_local_pilot_attestation(
        attestation,
        data_root=data_root,
        repo_root=ROOT,
    )

    print(f"STEP15_STATUS={attestation.status.value}")
    print(f"STEP15_ATTESTATION={attestation_path}")
    print(f"STEP15_DIGEST={attestation.digest()}")
    return exit_code if exit_code != 0 else (0 if attestation.passed else 1)


if __name__ == "__main__":
    raise SystemExit(main())
