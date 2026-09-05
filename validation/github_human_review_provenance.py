"""Collect runtime-only human-review provenance from authenticated GitHub comments.

The collector never creates an approval. It only materializes a receipt when GitHub's
API reports a matching comment authored by an independent human account and the comment
cryptographically binds itself to the exact repository review artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from validation.human_review_provenance import EXPECTED_REPOSITORY, GATE_ISSUES

_REVIEW_PATHS = {
    1: Path("docs/quality/reviews/extraction_gold_v1_review.json"),
    5: Path("docs/quality/reviews/reasoning_gold_v2_review.json"),
    16: Path("docs/quality/reviews/step_16_independent_review.json"),
    18: Path("docs/quality/reviews/step_18_independent_review.json"),
}
_CORPUS_REVIEW_FIELDS = (
    "annotation_review",
    "corpus_id",
    "corpus_sha256",
    "criticality_review",
    "decision",
    "freeze_approved",
    "iaa_required",
    "iaa_status",
    "reviewed_artifact_path",
    "reviewed_sha",
    "reviewer_id",
    "reviewer_independent",
    "reviewer_kind",
    "schema_version",
)
_AUTOMATION_RE = re.compile(
    r"(?:bot|factory|system|automated|automation|agent|github-actions)",
    re.I,
)


class GitHubProvenanceCollectionError(RuntimeError):
    """Raised only for collector/config/API failures, never for an absent approval."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GitHubProvenanceCollectionError(f"invalid review artifact: {path}") from exc
    if not isinstance(value, dict):
        raise GitHubProvenanceCollectionError(f"review artifact must be an object: {path}")
    return value


def _review_digest(step: int, path: Path, review: dict[str, object]) -> str:
    if step in {16, 18}:
        return _sha256(path)
    canonical = {name: review.get(name) for name in _CORPUS_REVIEW_FIELDS}
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _github_get_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lukart-ros-human-review-provenance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise GitHubProvenanceCollectionError(f"GitHub API request failed: {url}") from exc


def _issue_comments(repository: str, issue: int, token: str) -> list[dict[str, object]]:
    comments: list[dict[str, object]] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repository}/issues/{issue}/comments"
            f"?per_page=100&page={page}"
        )
        value = _github_get_json(url, token)
        if not isinstance(value, list):
            raise GitHubProvenanceCollectionError(
                "GitHub issue comments response must be a list"
            )
        batch = [item for item in value if isinstance(item, dict)]
        comments.extend(batch)
        if len(value) < 100:
            return comments
        page += 1


def _parse_attestation(body: object) -> dict[str, object] | None:
    if not isinstance(body, str):
        return None
    text = body.strip()
    marker = "LUKART_HUMAN_REVIEW_PROVENANCE_V1"
    if not text.startswith(marker):
        return None
    raw = text[len(marker) :].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[7:-3].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _independent_github_user(login: str, user_type: str, repository: str) -> bool:
    owner = repository.split("/", 1)[0].lower()
    normalized = login.strip().lower()
    return bool(
        user_type == "User"
        and normalized
        and normalized != owner
        and not normalized.endswith("[bot]")
        and _AUTOMATION_RE.search(normalized) is None
    )


def _matching_receipt(
    *,
    step: int,
    issue: int,
    repository: str,
    review: dict[str, object],
    review_sha256: str,
    comment: dict[str, object],
) -> dict[str, object] | None:
    user = comment.get("user")
    if not isinstance(user, dict):
        return None
    login = user.get("login")
    user_type = user.get("type")
    if not isinstance(login, str) or not isinstance(user_type, str):
        return None
    if not _independent_github_user(login, user_type, repository):
        return None

    attestation = _parse_attestation(comment.get("body"))
    if attestation is None:
        return None
    reviewed_sha = review.get("reviewed_sha")
    if not isinstance(reviewed_sha, str):
        return None
    expected = {
        "schema_version": "1.0",
        "step": step,
        "reviewer_id": login,
        "reviewer_kind": "human",
        "reviewer_independent": True,
        "decision": "PASS",
        "review_sha256": review_sha256,
        "reviewed_sha": reviewed_sha,
    }
    if any(attestation.get(name) != value for name, value in expected.items()):
        return None
    if review.get("reviewer_id") != login:
        return None
    if (
        review.get("reviewer_kind") != "human"
        or review.get("reviewer_independent") is not True
    ):
        return None
    if step in {1, 5}:
        if review.get("decision") != "APPROVED":
            return None
    elif review.get("decision") != "PASS":
        return None

    comment_id = comment.get("id")
    comment_url = comment.get("html_url")
    if not isinstance(comment_id, int) or not isinstance(comment_url, str) or not comment_url:
        return None
    return {
        "schema_version": "1.0",
        "verification_provider": "github_api",
        "source_kind": "github_issue_comment",
        "source_repository": repository,
        "source_issue": issue,
        "source_comment_id": comment_id,
        "source_comment_url": comment_url,
        "source_author_type": user_type,
        "source_author_login": login,
        "reviewer_id": login,
        "reviewer_kind": "human",
        "reviewer_independent": True,
        "decision": "PASS",
        "review_sha256": review_sha256,
        "reviewed_sha": reviewed_sha,
        "verified": True,
    }


def collect(root: Path, output_dir: Path, *, repository: str, token: str) -> int:
    if repository != EXPECTED_REPOSITORY:
        raise GitHubProvenanceCollectionError(
            f"unexpected repository {repository!r}; expected {EXPECTED_REPOSITORY!r}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    verified = 0
    for step, issue in GATE_ISSUES.items():
        review_path = root / _REVIEW_PATHS[step]
        if not review_path.is_file():
            continue
        review = _load_object(review_path)
        digest = _review_digest(step, review_path, review)
        receipt = None
        for comment in reversed(_issue_comments(repository, issue, token)):
            receipt = _matching_receipt(
                step=step,
                issue=issue,
                repository=repository,
                review=review,
                review_sha256=digest,
                comment=comment,
            )
            if receipt is not None:
                break
        if receipt is None:
            print(f"Step {step}: HUMAN_PROVENANCE_NOT_VERIFIED (issue #{issue})")
            continue
        target = output_dir / f"step_{step:02d}.json"
        target.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"Step {step}: HUMAN_PROVENANCE_VERIFIED "
            f"from comment {receipt['source_comment_id']}"
        )
        verified += 1
    return verified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token:
        raise GitHubProvenanceCollectionError("GITHUB_TOKEN is required")
    if not repository:
        raise GitHubProvenanceCollectionError("GITHUB_REPOSITORY is required")
    collect(Path(args.root), Path(args.output_dir), repository=repository, token=token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
