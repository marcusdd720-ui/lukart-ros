"""LRD-01Q immutable replay-revalidation baseline lineage v1.

This module chains already-verified LRD-01O baseline capsules through LRD-01P
transition records. It derives one exact current verified baseline from an ordered,
content-addressed lineage while rejecting forks, stale parents, reorderings and
tampering. It does not schedule replay, persist a mutable latest pointer, mutate
Product/CCL state, or grant release, storage/provider, policy, or certification
authority.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from core.p3.contracts import content_digest, require_hex_digest
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionState,
    ReplayRevalidationBaselineTransitionV1,
)
from core.replay_revalidation_baseline_v1 import (
    ReplayRevalidationBaselineError,
    ReplayRevalidationBaselineV1,
)

REVALIDATION_BASELINE_LINEAGE_SCHEMA_V1 = "lukart.replay-revalidation-baseline-lineage.v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReplayRevalidationBaselineLineageError(ValueError):
    """Fail-closed LRD-01Q contract violation."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationBaselineLineageError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationBaselineLineageError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationBaselineLineageError(
            f"{field} must be canonical lowercase sha256"
        )
    return normalized


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ReplayRevalidationBaselineLineageError(
            f"{field} must be a lowercase full Git SHA"
        )
    return text


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationBaselineLineageError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


_ENTRY_KEYS = frozenset({"transition", "resulting_baseline"})
_LINEAGE_KEYS = frozenset(
    {
        "schema",
        "genesis_baseline",
        "entries",
        "transition_digests",
        "transition_count",
        "successful_transition_count",
        "baseline_advance_count",
        "blocked_attempt_count",
        "current_baseline_digest",
        "current_repository_sha",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
        "persistence_authority",
        "mutable_pointer_authority",
        "lineage_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineLineageEntryV1:
    """One exact LRD-01P transition plus its resulting LRD-01O baseline, if any."""

    transition: ReplayRevalidationBaselineTransitionV1
    resulting_baseline: ReplayRevalidationBaselineV1 | None

    def __post_init__(self) -> None:
        if not isinstance(self.transition, ReplayRevalidationBaselineTransitionV1):
            raise ReplayRevalidationBaselineLineageError("entry transition has invalid type")
        transition = ReplayRevalidationBaselineTransitionV1.from_dict(
            self.transition.canonical_dict()
        )
        object.__setattr__(self, "transition", transition)

        expected = transition.resulting_baseline_digest
        if self.resulting_baseline is None:
            if expected is not None:
                raise ReplayRevalidationBaselineLineageError(
                    "successful transition requires exact resulting baseline evidence"
                )
            return
        try:
            baseline = ReplayRevalidationBaselineV1.from_dict(
                self.resulting_baseline.canonical_dict()
            )
        except ReplayRevalidationBaselineError as exc:
            raise ReplayRevalidationBaselineLineageError(
                f"invalid resulting baseline evidence: {exc}"
            ) from exc
        if expected is None:
            raise ReplayRevalidationBaselineLineageError(
                "blocked transition cannot carry resulting baseline evidence"
            )
        if baseline.baseline_digest != expected:
            raise ReplayRevalidationBaselineLineageError(
                "transition/resulting baseline digest mismatch"
            )
        object.__setattr__(self, "resulting_baseline", baseline)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "transition": self.transition.canonical_dict(),
            "resulting_baseline": (
                None
                if self.resulting_baseline is None
                else self.resulting_baseline.canonical_dict()
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationBaselineLineageEntryV1:
        _strict(value, _ENTRY_KEYS, field="revalidation baseline lineage entry")
        raw_transition = value.get("transition")
        if not isinstance(raw_transition, Mapping):
            raise ReplayRevalidationBaselineLineageError("entry transition must be an object")
        transition = ReplayRevalidationBaselineTransitionV1.from_dict(raw_transition)
        raw_baseline = value.get("resulting_baseline")
        baseline: ReplayRevalidationBaselineV1 | None
        if raw_baseline is None:
            baseline = None
        elif isinstance(raw_baseline, Mapping):
            try:
                baseline = ReplayRevalidationBaselineV1.from_dict(raw_baseline)
            except ReplayRevalidationBaselineError as exc:
                raise ReplayRevalidationBaselineLineageError(
                    f"invalid resulting baseline evidence: {exc}"
                ) from exc
        else:
            raise ReplayRevalidationBaselineLineageError(
                "resulting_baseline must be an object or null"
            )
        result = cls(transition=transition, resulting_baseline=baseline)
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationBaselineLineageError(
                "revalidation baseline lineage entry is not canonical"
            )
        return result


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineLineageV1:
    """Self-contained append-only lineage deriving one current verified baseline."""

    genesis_baseline: ReplayRevalidationBaselineV1
    entries: tuple[ReplayRevalidationBaselineLineageEntryV1, ...] = ()
    schema: str = REVALIDATION_BASELINE_LINEAGE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_BASELINE_LINEAGE_SCHEMA_V1:
            raise ReplayRevalidationBaselineLineageError(
                f"unsupported lineage schema: {self.schema}"
            )
        try:
            genesis = ReplayRevalidationBaselineV1.from_dict(
                self.genesis_baseline.canonical_dict()
            )
        except ReplayRevalidationBaselineError as exc:
            raise ReplayRevalidationBaselineLineageError(
                f"invalid genesis baseline evidence: {exc}"
            ) from exc
        object.__setattr__(self, "genesis_baseline", genesis)

        canonical_entries: list[ReplayRevalidationBaselineLineageEntryV1] = []
        seen: set[str] = set()
        current = genesis
        for index, raw_entry in enumerate(self.entries):
            if not isinstance(raw_entry, ReplayRevalidationBaselineLineageEntryV1):
                raise ReplayRevalidationBaselineLineageError(
                    f"entry[{index}] has invalid type"
                )
            entry = ReplayRevalidationBaselineLineageEntryV1.from_dict(
                raw_entry.canonical_dict()
            )
            transition = entry.transition
            if transition.transition_digest in seen:
                raise ReplayRevalidationBaselineLineageError(
                    f"duplicate transition at entry[{index}]"
                )
            seen.add(transition.transition_digest)
            if transition.prior_baseline_digest != current.baseline_digest:
                raise ReplayRevalidationBaselineLineageError(
                    f"entry[{index}] stale parent or lineage fork detected"
                )
            if transition.prior_repository_sha != current.repository_sha:
                raise ReplayRevalidationBaselineLineageError(
                    f"entry[{index}] prior repository SHA does not match current baseline"
                )

            if transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_REUSED:
                if entry.resulting_baseline != current:
                    raise ReplayRevalidationBaselineLineageError(
                        f"entry[{index}] BASELINE_REUSED must preserve exact baseline bytes"
                    )
                if transition.candidate_repository_sha != current.repository_sha:
                    raise ReplayRevalidationBaselineLineageError(
                        f"entry[{index}] BASELINE_REUSED repository SHA drift"
                    )
            elif transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED:
                if entry.resulting_baseline is None:
                    raise ReplayRevalidationBaselineLineageError(
                        f"entry[{index}] BASELINE_ADVANCED missing baseline evidence"
                    )
                if entry.resulting_baseline.repository_sha != transition.candidate_repository_sha:
                    raise ReplayRevalidationBaselineLineageError(
                        f"entry[{index}] advanced baseline repository SHA mismatch"
                    )
                current = entry.resulting_baseline
            elif entry.resulting_baseline is not None:
                raise ReplayRevalidationBaselineLineageError(
                    f"entry[{index}] blocked transition cannot advance baseline"
                )
            canonical_entries.append(entry)
        object.__setattr__(self, "entries", tuple(canonical_entries))

    @property
    def transition_digests(self) -> tuple[str, ...]:
        return tuple(entry.transition.transition_digest for entry in self.entries)

    @property
    def transition_count(self) -> int:
        return len(self.entries)

    @property
    def successful_transition_count(self) -> int:
        return sum(
            entry.transition.state
            in {
                ReplayRevalidationBaselineTransitionState.BASELINE_REUSED,
                ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED,
            }
            for entry in self.entries
        )

    @property
    def baseline_advance_count(self) -> int:
        return sum(
            entry.transition.state
            is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
            for entry in self.entries
        )

    @property
    def blocked_attempt_count(self) -> int:
        return self.transition_count - self.successful_transition_count

    @property
    def current_baseline(self) -> ReplayRevalidationBaselineV1:
        current = self.genesis_baseline
        for entry in self.entries:
            if (
                entry.transition.state
                is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
            ):
                assert entry.resulting_baseline is not None
                current = entry.resulting_baseline
        return current

    @property
    def current_baseline_digest(self) -> str:
        return self.current_baseline.baseline_digest

    @property
    def current_repository_sha(self) -> str:
        return self.current_baseline.repository_sha

    def append(
        self,
        entry: ReplayRevalidationBaselineLineageEntryV1,
    ) -> ReplayRevalidationBaselineLineageV1:
        """Return a fresh immutable lineage with one exact entry appended."""
        return ReplayRevalidationBaselineLineageV1(
            genesis_baseline=self.genesis_baseline,
            entries=(*self.entries, entry),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "genesis_baseline": self.genesis_baseline.canonical_dict(),
            "entries": [entry.canonical_dict() for entry in self.entries],
            "transition_digests": list(self.transition_digests),
            "transition_count": self.transition_count,
            "successful_transition_count": self.successful_transition_count,
            "baseline_advance_count": self.baseline_advance_count,
            "blocked_attempt_count": self.blocked_attempt_count,
            "current_baseline_digest": self.current_baseline_digest,
            "current_repository_sha": self.current_repository_sha,
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
            "storage_authority": False,
            "provider_authority": False,
            "persistence_authority": False,
            "mutable_pointer_authority": False,
        }

    @property
    def lineage_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "lineage_digest": self.lineage_digest}

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def build(
        cls,
        *,
        genesis_baseline: ReplayRevalidationBaselineV1,
        entries: Iterable[ReplayRevalidationBaselineLineageEntryV1] = (),
    ) -> ReplayRevalidationBaselineLineageV1:
        return cls(genesis_baseline=genesis_baseline, entries=tuple(entries))

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationBaselineLineageV1:
        _strict(value, _LINEAGE_KEYS, field="revalidation baseline lineage")
        for authority in (
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
            "storage_authority",
            "provider_authority",
            "persistence_authority",
            "mutable_pointer_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationBaselineLineageError(
                    f"{authority} must remain false"
                )

        raw_genesis = value.get("genesis_baseline")
        if not isinstance(raw_genesis, Mapping):
            raise ReplayRevalidationBaselineLineageError(
                "genesis_baseline must be an object"
            )
        try:
            genesis = ReplayRevalidationBaselineV1.from_dict(raw_genesis)
        except ReplayRevalidationBaselineError as exc:
            raise ReplayRevalidationBaselineLineageError(
                f"invalid genesis baseline evidence: {exc}"
            ) from exc

        raw_entries = value.get("entries")
        if not isinstance(raw_entries, list):
            raise ReplayRevalidationBaselineLineageError("entries must be a list")
        entries: list[ReplayRevalidationBaselineLineageEntryV1] = []
        for index, raw_entry in enumerate(raw_entries):
            if not isinstance(raw_entry, Mapping):
                raise ReplayRevalidationBaselineLineageError(
                    f"entry[{index}] must be an object"
                )
            entries.append(ReplayRevalidationBaselineLineageEntryV1.from_dict(raw_entry))

        result = cls(genesis_baseline=genesis, entries=tuple(entries))
        expected_digests = value.get("transition_digests")
        if expected_digests != list(result.transition_digests):
            raise ReplayRevalidationBaselineLineageError("transition_digests mismatch")
        for field, expected in (
            ("transition_count", result.transition_count),
            ("successful_transition_count", result.successful_transition_count),
            ("baseline_advance_count", result.baseline_advance_count),
            ("blocked_attempt_count", result.blocked_attempt_count),
        ):
            if value.get(field) != expected:
                raise ReplayRevalidationBaselineLineageError(f"{field} mismatch")
        if value.get("current_baseline_digest") != result.current_baseline_digest:
            raise ReplayRevalidationBaselineLineageError("current_baseline_digest mismatch")
        if value.get("current_repository_sha") != result.current_repository_sha:
            raise ReplayRevalidationBaselineLineageError("current_repository_sha mismatch")
        expected_lineage = _digest(value.get("lineage_digest"), field="lineage_digest")
        if result.lineage_digest != expected_lineage:
            raise ReplayRevalidationBaselineLineageError("lineage_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationBaselineLineageError(
                "revalidation baseline lineage is not canonical"
            )
        return result


def verify_revalidation_baseline_lineage_v1(
    lineage: ReplayRevalidationBaselineLineageV1,
) -> str:
    """Reparse exact canonical bytes and return the verified lineage digest."""
    try:
        parsed = json.loads(lineage.canonical_json_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayRevalidationBaselineLineageError(
            "lineage canonical JSON is invalid"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise ReplayRevalidationBaselineLineageError("lineage JSON root must be an object")
    restored = ReplayRevalidationBaselineLineageV1.from_dict(parsed)
    if restored != lineage:
        raise ReplayRevalidationBaselineLineageError("lineage round-trip mismatch")
    return restored.lineage_digest
