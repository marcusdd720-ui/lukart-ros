"""Post-v1 certification primitives.

This module is Factory-side validation. It observes Product artifacts and enforces release
contracts; it is not an alternate reasoning authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence


class CertificationError(ValueError):
    """Raised when a fail-closed Post-v1 certification contract is violated."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplayIdentity:
    code_sha: str
    config_version: str
    schema_version: str
    component_versions: tuple[str, ...]
    input_digest: str

    def __post_init__(self) -> None:
        required = (self.code_sha, self.config_version, self.schema_version, self.input_digest)
        if any(not value.strip() for value in required):
            raise CertificationError("replay identity fields cannot be blank")
        if len(self.input_digest) != 64:
            raise CertificationError("input_digest must be SHA-256")

    def digest(self) -> str:
        return content_digest(
            {
                "code_sha": self.code_sha,
                "config_version": self.config_version,
                "schema_version": self.schema_version,
                "component_versions": sorted(self.component_versions),
                "input_digest": self.input_digest,
            }
        )


def build_replay_identity(
    payload: object,
    *,
    code_sha: str,
    config_version: str,
    schema_version: str,
    component_versions: Sequence[str] = (),
) -> ReplayIdentity:
    return ReplayIdentity(
        code_sha=code_sha,
        config_version=config_version,
        schema_version=schema_version,
        component_versions=tuple(component_versions),
        input_digest=content_digest(payload),
    )


def verify_provenance_chain(records: Sequence[Mapping[str, object]]) -> bool:
    """Verify a deterministic hash chain.

    Each record contains payload, digest and parent_digest. The first parent_digest is null.
    A record digest is SHA-256 over {payload, parent_digest}.
    """

    previous: str | None = None
    for record in records:
        parent = record.get("parent_digest")
        if parent != previous:
            return False
        digest = record.get("digest")
        if not isinstance(digest, str) or len(digest) != 64:
            return False
        expected = content_digest({"payload": record.get("payload"), "parent_digest": parent})
        if digest != expected:
            return False
        previous = digest
    return True


def provenance_record(payload: object, parent_digest: str | None = None) -> dict[str, object]:
    digest = content_digest({"payload": payload, "parent_digest": parent_digest})
    return {"payload": payload, "parent_digest": parent_digest, "digest": digest}


_TRUSTED_STATES = frozenset({"FACT", "CERTIFIED", "TRUSTED"})


def require_controlled_promotion(
    *,
    source_state: str,
    target_state: str,
    validated: bool,
    approver_id: str | None,
    quarantined: bool,
) -> None:
    """Fail closed for candidate/self-healing promotion into trusted state."""

    if target_state.upper() not in _TRUSTED_STATES:
        return
    if source_state.upper() in _TRUSTED_STATES:
        return
    if quarantined:
        raise CertificationError("quarantined candidate cannot be promoted")
    if not validated:
        raise CertificationError("trusted-state promotion requires validation")
    if not approver_id or not approver_id.strip():
        raise CertificationError("trusted-state promotion requires explicit approver identity")


def semantic_renderer_fidelity(
    source: Mapping[str, object], rendered: Mapping[str, object]
) -> tuple[bool, tuple[str, ...]]:
    """Compare semantic fields which a renderer is forbidden to rewrite or drop."""

    issues: list[str] = []
    for key in ("status", "evidence_refs", "open_questions", "contradictions"):
        if key in source and rendered.get(key) != source.get(key):
            issues.append(f"renderer changed semantic field: {key}")
    if "certainty" in source:
        source_certainty = source.get("certainty")
        rendered_certainty = rendered.get("certainty", source_certainty)
        if isinstance(source_certainty, (int, float)) and isinstance(rendered_certainty, (int, float)):
            if rendered_certainty > source_certainty:
                issues.append("renderer increased certainty")
    return not issues, tuple(issues)


def kqm_release_decision(
    metrics: Mapping[str, float], thresholds: Mapping[str, Mapping[str, float | str]]
) -> tuple[bool, tuple[str, ...]]:
    """Evaluate versioned KQM thresholds without mutating Product state."""

    failures: list[str] = []
    for name, policy in sorted(thresholds.items()):
        if name not in metrics:
            failures.append(f"missing metric: {name}")
            continue
        value = float(metrics[name])
        release = float(policy["release_threshold"])
        direction = str(policy.get("direction", "min"))
        if direction == "min" and value < release:
            failures.append(f"{name} below release threshold")
        elif direction == "max" and value > release:
            failures.append(f"{name} above release threshold")
        elif direction not in {"min", "max"}:
            raise CertificationError(f"unsupported threshold direction for {name}: {direction}")
    return not failures, tuple(failures)


def hostile_evidence_is_data(text: str) -> bool:
    """Factory policy marker: document instructions are never execution authority.

    This intentionally does not attempt to classify every possible prompt injection. It marks
    evidence as inert data and is consumed by security tests/pipeline policy.
    """

    return isinstance(text, str)
