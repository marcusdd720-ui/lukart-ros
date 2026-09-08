"""LRD-01A replay-closure coverage contract.

This module is measurement and architecture evidence only. It does not write Product state,
CCL history, Gold, authorization policy, trust state, or release state.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from core.p3.contracts import canonical_json

REPLAY_CLOSURE_COVERAGE_SCHEMA_V1 = "lukart.replay-closure-coverage.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_LRD_TRUST_CRITICAL_ITEMS = tuple(
    sorted(
        {
            "artifact_escrow_backend",
            "artifact_escrow_durability",
            "authorization_policy_identities",
            "canonicalization_profiles",
            "code_sha_tree",
            "config",
            "crypto_algorithms_profiles",
            "crypto_renewal_attestations",
            "dependencies",
            "epistemic_trust_policies",
            "evidence_input_digests",
            "exact_external_responses",
            "exact_requests",
            "lockfiles",
            "migration_chains",
            "offline_network_boundary",
            "offline_verifier",
            "plugins",
            "providers_models",
            "python_runtime_environment",
            "renderer_identity",
            "sbom",
            "schemas",
            "semantic_result_identity",
            "source_archive",
            "storage_identity",
            "supersession_lineage",
            "tenant_case_isolation",
            "verification_material",
            "wheels_sdists",
        }
    )
)

_ITEM_KEYS = frozenset(
    {
        "item_id",
        "classifications",
        "evidence_refs",
        "current_state",
        "required_action",
        "exact_replay_required",
        "fail_closed_outcome",
    }
)
_MATRIX_KEYS = frozenset({"schema", "baseline_main_sha", "items"})


class ReplayClosureCoverageError(ValueError):
    """Fail-closed replay-closure coverage contract violation."""


class ReplayCoverageClassification(StrEnum):
    """Orthogonal Phase-0 classification tags required by the LRD contract."""

    BOUND = "BOUND"
    UNBOUND = "UNBOUND"
    EXTERNAL = "EXTERNAL"
    PRESERVED = "PRESERVED"
    REGENERATABLE = "REGENERATABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ReplayFailClosedOutcome(StrEnum):
    """Permitted outcomes when a trust-critical identity cannot be established."""

    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    UNVERIFIABLE = "UNVERIFIABLE"
    ABSTAIN = "ABSTAIN"


def _copy_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise ReplayClosureCoverageError(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise ReplayClosureCoverageError(
            f"{field_name} is not canonically serializable"
        ) from exc
    if not isinstance(decoded, dict):
        raise ReplayClosureCoverageError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _require_exact_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    missing = tuple(sorted(expected - actual))
    unknown = tuple(sorted(actual - expected))
    if not missing and not unknown:
        return
    parts: list[str] = []
    if missing:
        parts.append("missing=" + ",".join(missing))
    if unknown:
        parts.append("unknown=" + ",".join(unknown))
    raise ReplayClosureCoverageError(
        f"{field_name} key contract violation: " + "; ".join(parts)
    )


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayClosureCoverageError(f"{field_name} must be a nonblank string")
    if value != value.strip():
        raise ReplayClosureCoverageError(f"{field_name} must be canonical without whitespace")
    return value


def _string_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ReplayClosureCoverageError(f"{field_name} must be a sequence")
    result = tuple(_text(item, field_name=field_name) for item in value)
    if not result:
        raise ReplayClosureCoverageError(f"{field_name} cannot be empty")
    if tuple(sorted(set(result))) != result:
        raise ReplayClosureCoverageError(f"{field_name} must be unique and sorted")
    return result


@dataclass(frozen=True, slots=True)
class ReplayClosureCoverageItemV1:
    """One measured trust-critical replay dependency."""

    item_id: str
    classifications: tuple[ReplayCoverageClassification, ...]
    evidence_refs: tuple[str, ...]
    current_state: str
    required_action: str
    exact_replay_required: bool
    fail_closed_outcome: ReplayFailClosedOutcome

    def __post_init__(self) -> None:
        _text(self.item_id, field_name="item_id")
        if not self.classifications:
            raise ReplayClosureCoverageError("classifications cannot be empty")
        values = tuple(item.value for item in self.classifications)
        if tuple(sorted(set(values))) != values:
            raise ReplayClosureCoverageError(
                "classifications must be unique and sorted"
            )
        _string_tuple(self.evidence_refs, field_name="evidence_refs")
        _text(self.current_state, field_name="current_state")
        _text(self.required_action, field_name="required_action")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayClosureCoverageItemV1:
        raw = _copy_mapping(value, field_name="coverage item")
        _require_exact_keys(raw, expected=_ITEM_KEYS, field_name="coverage item")
        classification_values = _string_tuple(
            raw.get("classifications"),
            field_name="classifications",
        )
        try:
            classifications = tuple(
                ReplayCoverageClassification(item) for item in classification_values
            )
            outcome = ReplayFailClosedOutcome(
                _text(raw.get("fail_closed_outcome"), field_name="fail_closed_outcome")
            )
        except ValueError as exc:
            raise ReplayClosureCoverageError("unknown replay coverage enum value") from exc
        exact_replay_required = raw.get("exact_replay_required")
        if not isinstance(exact_replay_required, bool):
            raise ReplayClosureCoverageError("exact_replay_required must be boolean")
        return cls(
            item_id=_text(raw.get("item_id"), field_name="item_id"),
            classifications=classifications,
            evidence_refs=_string_tuple(raw.get("evidence_refs"), field_name="evidence_refs"),
            current_state=_text(raw.get("current_state"), field_name="current_state"),
            required_action=_text(raw.get("required_action"), field_name="required_action"),
            exact_replay_required=exact_replay_required,
            fail_closed_outcome=outcome,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "classifications": [item.value for item in self.classifications],
            "evidence_refs": list(self.evidence_refs),
            "current_state": self.current_state,
            "required_action": self.required_action,
            "exact_replay_required": self.exact_replay_required,
            "fail_closed_outcome": self.fail_closed_outcome.value,
        }


@dataclass(frozen=True, slots=True)
class ReplayClosureCoverageMatrixV1:
    """Complete LRD-01A Phase-0 measurement with a content-derived identity."""

    baseline_main_sha: str
    items: tuple[ReplayClosureCoverageItemV1, ...]
    schema: str = REPLAY_CLOSURE_COVERAGE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REPLAY_CLOSURE_COVERAGE_SCHEMA_V1:
            raise ReplayClosureCoverageError(f"unsupported coverage schema: {self.schema}")
        if _SHA256_RE.fullmatch(self.baseline_main_sha) is None:
            raise ReplayClosureCoverageError("baseline_main_sha must be a lowercase full SHA")
        item_ids = tuple(item.item_id for item in self.items)
        if tuple(sorted(set(item_ids))) != item_ids:
            raise ReplayClosureCoverageError("coverage items must be unique and sorted")
        required = set(REQUIRED_LRD_TRUST_CRITICAL_ITEMS)
        actual = set(item_ids)
        if actual != required:
            missing = tuple(sorted(required - actual))
            unknown = tuple(sorted(actual - required))
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if unknown:
                details.append("unknown=" + ",".join(unknown))
            raise ReplayClosureCoverageError(
                "trust-critical coverage is incomplete: " + "; ".join(details)
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayClosureCoverageMatrixV1:
        raw = _copy_mapping(value, field_name="coverage matrix")
        _require_exact_keys(raw, expected=_MATRIX_KEYS, field_name="coverage matrix")
        if raw.get("schema") != REPLAY_CLOSURE_COVERAGE_SCHEMA_V1:
            raise ReplayClosureCoverageError("unsupported coverage matrix schema")
        raw_items = raw.get("items")
        if not isinstance(raw_items, list):
            raise ReplayClosureCoverageError("coverage matrix items must be a list")
        items: list[ReplayClosureCoverageItemV1] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, Mapping):
                raise ReplayClosureCoverageError(
                    f"coverage matrix item {index} must be an object"
                )
            items.append(
                ReplayClosureCoverageItemV1.from_dict(cast(Mapping[str, object], item))
            )
        return cls(
            baseline_main_sha=_text(
                raw.get("baseline_main_sha"),
                field_name="baseline_main_sha",
            ),
            items=tuple(items),
        )

    @property
    def coverage_percentage(self) -> int:
        return (len(self.items) * 100) // len(REQUIRED_LRD_TRUST_CRITICAL_ITEMS)

    @property
    def design_gate_pass(self) -> bool:
        return self.coverage_percentage == 100

    @property
    def gap_item_ids(self) -> tuple[str, ...]:
        gap_tags = {
            ReplayCoverageClassification.UNBOUND,
            ReplayCoverageClassification.EXTERNAL,
            ReplayCoverageClassification.UNAVAILABLE,
        }
        return tuple(
            item.item_id for item in self.items if gap_tags.intersection(item.classifications)
        )

    @property
    def exact_replay_gap_item_ids(self) -> tuple[str, ...]:
        gap_ids = set(self.gap_item_ids)
        return tuple(
            item.item_id
            for item in self.items
            if item.exact_replay_required and item.item_id in gap_ids
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "baseline_main_sha": self.baseline_main_sha,
            "items": [item.canonical_dict() for item in self.items],
        }

    @property
    def matrix_identity(self) -> str:
        payload = canonical_json(self.canonical_dict()).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_replay_closure_coverage_matrix(
    path: str | Path,
) -> ReplayClosureCoverageMatrixV1:
    """Load and validate the strict LRD-01A matrix without implicit fallback."""

    try:
        decoded: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayClosureCoverageError("cannot load replay closure coverage matrix") from exc
    if not isinstance(decoded, Mapping):
        raise ReplayClosureCoverageError("coverage matrix root must be an object")
    return ReplayClosureCoverageMatrixV1.from_dict(cast(Mapping[str, object], decoded))
