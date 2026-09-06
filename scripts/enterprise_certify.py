from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core.enterprise.certification import ControlEvidence, EnterpriseCertificationGate
from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]

_STAGE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "E0": (
        "MASTER_PLAN.md",
        "docs/ENTERPRISE_ROADMAP.md",
        "config/enterprise_v1.json",
        "pyproject.toml",
        ".github/workflows/mvros-v1-release.yml",
    ),
    "E1": (
        "config/enterprise_threat_model_v1.json",
        "scripts/enterprise_threat_check.py",
        "core/enterprise/contracts.py",
    ),
    "E2": ("core/enterprise/isolation.py",),
    "E3": ("core/enterprise/contracts.py",),
    "E4": (
        "core/enterprise/supply_chain.py",
        ".github/workflows/enterprise-codeql.yml",
        ".github/workflows/enterprise-hardening.yml",
        "build/enterprise/bom.cdx.json",
    ),
    "E5": ("core/enterprise/authorization.py",),
    "E6": ("core/enterprise/durability.py",),
    "E7": ("core/enterprise/observability.py",),
    "E8": ("core/enterprise/api_guard.py",),
    "E9": (
        "core/enterprise/resilience.py",
        "core/p3/scale.py",
        "build/enterprise/scale-certification.json",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_engineering_evidence(candidate_sha: str) -> dict[str, object]:
    sha = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40, 64))
    controls: list[ControlEvidence] = []
    artifacts_by_stage: dict[str, dict[str, str]] = {}

    for stage in sorted(_STAGE_ARTIFACTS):
        artifact_hashes: dict[str, str] = {}
        for relative in _STAGE_ARTIFACTS[stage]:
            path = ROOT / relative
            if not path.is_file():
                raise RuntimeError(f"missing Enterprise evidence artifact: {relative}")
            artifact_hashes[relative] = _sha256(path)
        artifacts_by_stage[stage] = artifact_hashes
        stage_digest = content_digest(
            {
                "candidate_sha": sha,
                "stage": stage,
                "artifacts": artifact_hashes,
            }
        )
        controls.append(
            ControlEvidence(
                stage=stage,
                passed=True,
                evidence_digest=stage_digest,
                detail="validated by preceding exact-SHA Enterprise gate steps",
            )
        )

    result = EnterpriseCertificationGate().evaluate(candidate_sha=sha, evidence=controls)
    if result.state.value != "INDEPENDENT_REVIEW_REQUIRED":
        raise RuntimeError(f"unexpected Enterprise engineering gate state: {result.state.value}")

    return {
        "schema": "lukart.enterprise-engineering-evidence.v1",
        "candidate_sha": sha,
        "state": result.state.value,
        "evidence_bundle_digest": result.evidence_bundle_digest,
        "missing_stages": list(result.missing_stages),
        "failed_stages": list(result.failed_stages),
        "independent_review_digest": result.independent_review_digest,
        "controls": [item.canonical_dict() for item in controls],
        "artifacts": artifacts_by_stage,
        "claim_boundary": (
            "Automated engineering evidence only; independent Enterprise certification "
            "requires separately signed review evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build exact-SHA Enterprise engineering evidence")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/enterprise/enterprise-engineering-evidence.json",
    )
    args = parser.parse_args()

    evidence = build_engineering_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ENTERPRISE_ENGINEERING_STATE={evidence['state']}")
    print(f"ENTERPRISE_EVIDENCE_BUNDLE_DIGEST={evidence['evidence_bundle_digest']}")
    print(f"ENTERPRISE_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
