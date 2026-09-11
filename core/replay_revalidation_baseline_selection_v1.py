"""LRD-01R append-only operational selection of verified revalidation lineages.

This module persists which already-verified LRD-01Q lineage is operationally
selected. Selection state is derived from a verified append-only provenance stream;
there is no mutable latest pointer. Persistence reuses SQLiteProvenanceStore and its
transactional compare-and-append primitive. The contract grants no scheduler,
release, Product/CCL write, provider, or artifact-storage authority.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import DurableRecord, SQLiteProvenanceStore
from core.p3.contracts import content_digest, require_hex_digest
from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageError,
    ReplayRevalidationBaselineLineageV1,
    verify_revalidation_baseline_lineage_v1,
)

REVALIDATION_BASELINE_SELECTION_SCHEMA_V1 = (
    "lukart.replay-revalidation-baseline-selection.v1"
)
REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1 = (
    "system:lrd-revalidation-baseline-selection:v1"
)
REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1 = (
    "lrd.revalidation-baseline-selection.v1"
)
_SELECTION_GENESIS = "0" * 64
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReplayRevalidationBaselineSelectionError(ValueError):
    """Fail-closed LRD-01R contract violation."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationBaselineSelectionError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationBaselineSelectionError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationBaselineSelectionError(
            f"{field} must be canonical lowercase sha256"
        )
    return normalized


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ReplayRevalidationBaselineSelectionError(
            f"{field} must be a lowercase full Git SHA"
        )
    return text


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationBaselineSelectionError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


_SELECTION_KEYS = frozenset(
    {
        "schema",
        "lineage",
        "lineage_digest",
        "current_baseline_digest",
        "current_repository_sha",
        "previous_selection_digest",
        "selection_persistence_authority",
        "mutable_pointer_authority",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
        "selection_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineSelectionV1:
    """One self-contained selection of an exact verified LRD-01Q lineage."""

    lineage: ReplayRevalidationBaselineLineageV1
    previous_selection_digest: str = _SELECTION_GENESIS
    schema: str = REVALIDATION_BASELINE_SELECTION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_BASELINE_SELECTION_SCHEMA_V1:
            raise ReplayRevalidationBaselineSelectionError(
                f"unsupported selection schema: {self.schema}"
            )
        try:
            lineage = ReplayRevalidationBaselineLineageV1.from_dict(
                self.lineage.canonical_dict()
            )
            verify_revalidation_baseline_lineage_v1(lineage)
        except ReplayRevalidationBaselineLineageError as exc:
            raise ReplayRevalidationBaselineSelectionError(
                f"invalid selected lineage: {exc}"
            ) from exc
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(
            self,
            "previous_selection_digest",
            _digest(
                self.previous_selection_digest,
                field="previous_selection_digest",
            ),
        )

    @property
    def lineage_digest(self) -> str:
        return self.lineage.lineage_digest

    @property
    def current_baseline_digest(self) -> str:
        return self.lineage.current_baseline_digest

    @property
    def current_repository_sha(self) -> str:
        return self.lineage.current_repository_sha

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "lineage": self.lineage.canonical_dict(),
            "lineage_digest": self.lineage_digest,
            "current_baseline_digest": self.current_baseline_digest,
            "current_repository_sha": self.current_repository_sha,
            "previous_selection_digest": self.previous_selection_digest,
            "selection_persistence_authority": True,
            "mutable_pointer_authority": False,
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
            "storage_authority": False,
            "provider_authority": False,
        }

    @property
    def selection_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "selection_digest": self.selection_digest}

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationBaselineSelectionV1:
        _strict(value, _SELECTION_KEYS, field="revalidation baseline selection")
        if value.get("selection_persistence_authority") is not True:
            raise ReplayRevalidationBaselineSelectionError(
                "selection_persistence_authority must remain true"
            )
        for authority in (
            "mutable_pointer_authority",
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
            "storage_authority",
            "provider_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationBaselineSelectionError(
                    f"{authority} must remain false"
                )

        raw_lineage = value.get("lineage")
        if not isinstance(raw_lineage, Mapping):
            raise ReplayRevalidationBaselineSelectionError("lineage must be an object")
        try:
            lineage = ReplayRevalidationBaselineLineageV1.from_dict(raw_lineage)
        except ReplayRevalidationBaselineLineageError as exc:
            raise ReplayRevalidationBaselineSelectionError(
                f"invalid selected lineage: {exc}"
            ) from exc
        result = cls(
            lineage=lineage,
            previous_selection_digest=_digest(
                value.get("previous_selection_digest"),
                field="previous_selection_digest",
            ),
        )
        if value.get("lineage_digest") != result.lineage_digest:
            raise ReplayRevalidationBaselineSelectionError("lineage_digest mismatch")
        if value.get("current_baseline_digest") != result.current_baseline_digest:
            raise ReplayRevalidationBaselineSelectionError(
                "current_baseline_digest mismatch"
            )
        repository_sha = _git_sha(
            value.get("current_repository_sha"),
            field="current_repository_sha",
        )
        if repository_sha != result.current_repository_sha:
            raise ReplayRevalidationBaselineSelectionError(
                "current_repository_sha mismatch"
            )
        expected_selection = _digest(
            value.get("selection_digest"),
            field="selection_digest",
        )
        if expected_selection != result.selection_digest:
            raise ReplayRevalidationBaselineSelectionError("selection_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationBaselineSelectionError(
                "revalidation baseline selection is not canonical"
            )
        return result


def verify_revalidation_baseline_selection_v1(
    selection: ReplayRevalidationBaselineSelectionV1,
) -> str:
    """Reparse exact canonical bytes and return the verified semantic digest."""
    try:
        parsed = json.loads(selection.canonical_json_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayRevalidationBaselineSelectionError(
            "selection canonical JSON is invalid"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise ReplayRevalidationBaselineSelectionError(
            "selection JSON root must be an object"
        )
    restored = ReplayRevalidationBaselineSelectionV1.from_dict(parsed)
    if restored != selection:
        raise ReplayRevalidationBaselineSelectionError("selection round-trip mismatch")
    return restored.selection_digest


def _require_strict_extension(
    previous: ReplayRevalidationBaselineLineageV1,
    candidate: ReplayRevalidationBaselineLineageV1,
) -> None:
    if candidate.genesis_baseline != previous.genesis_baseline:
        raise ReplayRevalidationBaselineSelectionError(
            "selected lineage genesis baseline changed"
        )
    if len(candidate.entries) <= len(previous.entries):
        if candidate == previous:
            raise ReplayRevalidationBaselineSelectionError(
                "duplicate selected lineage is a no-op"
            )
        raise ReplayRevalidationBaselineSelectionError(
            "selected lineage rollback is not allowed"
        )
    prefix = candidate.entries[: len(previous.entries)]
    if prefix != previous.entries:
        raise ReplayRevalidationBaselineSelectionError(
            "selected lineage must be an exact extension; fork or reorder detected"
        )


class ReplayRevalidationBaselineSelectionLedgerV1:
    """Operational selection view backed by one existing provenance store."""

    def __init__(self, store: SQLiteProvenanceStore) -> None:
        if not isinstance(store, SQLiteProvenanceStore):
            raise ReplayRevalidationBaselineSelectionError(
                "selection ledger requires SQLiteProvenanceStore"
            )
        self._store = store

    def _selection_records(self) -> tuple[DurableRecord, ...]:
        try:
            records = self._store.verify()
        except EnterpriseContractError as exc:
            raise ReplayRevalidationBaselineSelectionError(
                f"durable provenance verification failed: {exc}"
            ) from exc
        return tuple(
            record
            for record in records
            if record.stream_id == REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
        )

    def selections(self) -> tuple[ReplayRevalidationBaselineSelectionV1, ...]:
        """Verify durable and semantic chains and return ordered selections."""
        verified: list[ReplayRevalidationBaselineSelectionV1] = []
        previous_digest = _SELECTION_GENESIS
        previous_lineage: ReplayRevalidationBaselineLineageV1 | None = None
        seen: set[str] = set()
        for index, record in enumerate(self._selection_records()):
            if record.event_type != REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1:
                raise ReplayRevalidationBaselineSelectionError(
                    f"selection record[{index}] has unknown event type"
                )
            try:
                selection = ReplayRevalidationBaselineSelectionV1.from_dict(
                    record.payload
                )
            except ReplayRevalidationBaselineSelectionError as exc:
                raise ReplayRevalidationBaselineSelectionError(
                    f"invalid selection record[{index}]: {exc}"
                ) from exc
            if selection.previous_selection_digest != previous_digest:
                raise ReplayRevalidationBaselineSelectionError(
                    f"selection record[{index}] previous selection digest mismatch"
                )
            if selection.selection_digest in seen:
                raise ReplayRevalidationBaselineSelectionError(
                    f"duplicate selection digest at record[{index}]"
                )
            if previous_lineage is not None:
                _require_strict_extension(previous_lineage, selection.lineage)
            seen.add(selection.selection_digest)
            verified.append(selection)
            previous_digest = selection.selection_digest
            previous_lineage = selection.lineage
        return tuple(verified)

    def current_selection(self) -> ReplayRevalidationBaselineSelectionV1 | None:
        """Derive current authority from the verified log tail, never a pointer."""
        selections = self.selections()
        return selections[-1] if selections else None

    def append(
        self,
        lineage: ReplayRevalidationBaselineLineageV1,
    ) -> ReplayRevalidationBaselineSelectionV1:
        """Persist a verified first selection or strict lineage extension."""
        try:
            canonical_lineage = ReplayRevalidationBaselineLineageV1.from_dict(
                lineage.canonical_dict()
            )
            verify_revalidation_baseline_lineage_v1(canonical_lineage)
        except (AttributeError, ReplayRevalidationBaselineLineageError) as exc:
            raise ReplayRevalidationBaselineSelectionError(
                f"invalid lineage selection candidate: {exc}"
            ) from exc

        selections = self.selections()
        if selections:
            previous = selections[-1]
            _require_strict_extension(previous.lineage, canonical_lineage)
            previous_digest = previous.selection_digest
        else:
            previous_digest = _SELECTION_GENESIS

        selection = ReplayRevalidationBaselineSelectionV1(
            lineage=canonical_lineage,
            previous_selection_digest=previous_digest,
        )
        verify_revalidation_baseline_selection_v1(selection)
        try:
            expected_head = self._store.stream_head_digest(
                REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
            )
            self._store.append(
                stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
                event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
                payload=selection.canonical_dict(),
                expected_stream_head=expected_head,
            )
        except EnterpriseContractError as exc:
            raise ReplayRevalidationBaselineSelectionError(
                f"selection compare-and-append failed: {exc}"
            ) from exc

        persisted = self.current_selection()
        if persisted != selection:
            raise ReplayRevalidationBaselineSelectionError(
                "persisted selection identity mismatch"
            )
        return selection
