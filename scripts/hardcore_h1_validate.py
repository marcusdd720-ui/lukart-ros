from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

from core.p3.contracts import require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RELEASE_TAG = "v1.0.1"
POLICY_PATH = "config/enterprise_v1.json"
WORKFLOW_PATH = ".github/workflows/enterprise-hardening.yml"
BASELINE_DOCUMENTS = (
    "MASTER_PLAN.md",
    "docs/ROADMAP_V1_1.md",
    "docs/ENTERPRISE_ROADMAP.md",
)
_RELEASE_COMMIT_PATTERN = re.compile(r"v1\.0\.1\s*@\s*([0-9a-f]{40})")
_TAG_OBJECT_PATTERN = re.compile(r"v1\.0\.1\s+tag object\s*@\s*([0-9a-f]{40})")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(payload: str) -> str:
    return _sha256_bytes(payload.encode("utf-8"))


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _document_release_commit_shas(text: str) -> set[str]:
    return set(_RELEASE_COMMIT_PATTERN.findall(text))


def _document_tag_object_shas(text: str) -> set[str]:
    return set(_TAG_OBJECT_PATTERN.findall(text))


def validate_snapshot(
    *,
    candidate_sha: str,
    head_sha: str,
    tag_object_sha: str,
    release_commit_sha: str,
    policy: Mapping[str, object],
    documents: Mapping[str, str],
    workflow_text: str,
) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(head_sha, field_name="head_sha", lengths=(40,))
    tag_object = require_hex_digest(
        tag_object_sha,
        field_name="historical_release_tag_object_sha",
        lengths=(40,),
    )
    release_commit = require_hex_digest(
        release_commit_sha,
        field_name="historical_release_commit_sha",
        lengths=(40,),
    )

    if head != candidate:
        raise RuntimeError(
            f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}"
        )

    baseline = policy.get("baseline")
    if not isinstance(baseline, Mapping):
        raise RuntimeError("Enterprise policy baseline section is missing")
    configured_release_commit = require_hex_digest(
        str(baseline.get("v1_0_1_sha", "")),
        field_name="policy.baseline.v1_0_1_sha",
        lengths=(40,),
    )
    configured_tag_object = require_hex_digest(
        str(baseline.get("v1_0_1_tag_object_sha", "")),
        field_name="policy.baseline.v1_0_1_tag_object_sha",
        lengths=(40,),
    )
    if configured_release_commit != release_commit:
        raise RuntimeError(
            "historical release commit identity mismatch: "
            f"policy={configured_release_commit} git-tag-target={release_commit}"
        )
    if configured_tag_object != tag_object:
        raise RuntimeError(
            "historical annotated tag identity mismatch: "
            f"policy={configured_tag_object} git-tag-object={tag_object}"
        )
    if baseline.get("v1_0_1_immutable") is not True:
        raise RuntimeError("historical v1.0.1 baseline is not marked immutable")

    document_digests: dict[str, str] = {}
    for path in BASELINE_DOCUMENTS:
        text = documents.get(path)
        if text is None:
            raise RuntimeError(f"missing canonical baseline document: {path}")
        declared_commits = _document_release_commit_shas(text)
        if declared_commits != {release_commit}:
            raise RuntimeError(
                "canonical release commit drift in "
                f"{path}: declared={sorted(declared_commits)} expected={release_commit}"
            )
        declared_tag_objects = _document_tag_object_shas(text)
        if declared_tag_objects != {tag_object}:
            raise RuntimeError(
                "canonical annotated tag drift in "
                f"{path}: declared={sorted(declared_tag_objects)} expected={tag_object}"
            )
        document_digests[path] = _sha256_text(text)

    if "  push:\n    branches: [main]" not in workflow_text:
        raise RuntimeError("Enterprise workflow lacks post-merge push validation for main")
    if "fetch-depth: 0" not in workflow_text:
        raise RuntimeError(
            "Enterprise workflow cannot verify historical tag without full tag/history fetch"
        )

    return {
        "schema": "lukart.hardcore-h1-evidence.v2",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "historical_release_tag": HISTORICAL_RELEASE_TAG,
        "historical_release_tag_object_sha": tag_object,
        "historical_release_commit_sha": release_commit,
        "policy_release_commit_sha": configured_release_commit,
        "policy_tag_object_sha": configured_tag_object,
        "canonical_document_digests": document_digests,
        "enterprise_workflow_digest": _sha256_text(workflow_text),
        "state": "CONTROL_PASS",
    }


def build_h1_evidence(candidate_sha: str) -> dict[str, object]:
    head_sha = _git("rev-parse", "HEAD")
    try:
        tag_type = _git("cat-file", "-t", HISTORICAL_RELEASE_TAG)
        tag_object_sha = _git("rev-parse", HISTORICAL_RELEASE_TAG)
        release_commit_sha = _git("rev-parse", f"{HISTORICAL_RELEASE_TAG}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"historical release tag {HISTORICAL_RELEASE_TAG} is unavailable in checkout"
        ) from exc
    if tag_type != "tag":
        raise RuntimeError(
            f"historical release tag {HISTORICAL_RELEASE_TAG} is not an annotated tag"
        )

    policy = json.loads((ROOT / POLICY_PATH).read_text(encoding="utf-8"))
    documents = {
        path: (ROOT / path).read_text(encoding="utf-8") for path in BASELINE_DOCUMENTS
    }
    workflow_text = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")
    return validate_snapshot(
        candidate_sha=candidate_sha,
        head_sha=head_sha,
        tag_object_sha=tag_object_sha,
        release_commit_sha=release_commit_sha,
        policy=policy,
        documents=documents,
        workflow_text=workflow_text,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate H1 exact-SHA and immutable baseline integrity"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/h1-baseline-evidence.json",
    )
    args = parser.parse_args()

    evidence = build_h1_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H1_EXACT_SHA_BASELINE_INTEGRITY=PASS")
    print(f"H1_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H1_TAG_OBJECT_SHA={evidence['historical_release_tag_object_sha']}")
    print(f"H1_RELEASE_COMMIT_SHA={evidence['historical_release_commit_sha']}")
    print(f"H1_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
