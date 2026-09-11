"""LRD-01S caller-invoked handoff from selected baseline to selected lineage.

The handoff composes existing LRD-01M/01N/01P/01Q/01R authorities. It always
derives the prior baseline from the currently verified 01R selection, produces one
exact transition, extends that selected lineage by exactly one entry, and persists
that extension through the existing 01R selection ledger. It does not discover
changes, execute replay, schedule or dispatch work, mutate Product/CCL state, grant
provider/storage authority, or create another persistence stream.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from core.p3.contracts import RuntimeIdentity, content_digest, require_hex_digest
from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageEntryV1,
    ReplayRevalidationBaselineLineageError,
)
from core.replay_revalidation_baseline_selection_v1 import (
    ReplayRevalidationBaselineSelectionError,
    ReplayRevalidationBaselineSelectionLedgerV1,
    ReplayRevalidationBaselineSelectionV1,
    verify_revalidation_baseline_selection_v1,
)
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionError,
    ReplayRevalidationBaselineTransitionState,
    ReplayRevalidationBaselineTransitionV1,
    evaluate_revalidation_baseline_transition_v1,
)
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentError,
    ReplayRevalidationFulfilmentV1,
    evaluate_revalidation_fulfilment_v1,
)
from core.replay_revalidation_invalidation_v1 import (
    ReplayRevalidationDecisionV1,
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
    evaluate_revalidation_requirement_v1,
)

REVALIDATION_SELECTED_HANDOFF_SCHEMA_V1 = "lukart.replay-revalidation-selected-handoff.v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReplayRevalidationSelectedHandoffError(ValueError):
    """Fail-closed LRD-01S contract violation."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationSelectedHandoffError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationSelectedHandoffError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationSelectedHandoffError(
            f"{field} must be canonical lowercase sha256"
        )
    return normalized


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ReplayRevalidationSelectedHandoffError(
            f"{field} must be a lowercase full Git SHA"
        )
    return text


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationSelectedHandoffError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


_HANDOFF_KEYS = frozenset(
    {
        "schema",
        "source_selection",
        "source_selection_digest",
        "candidate_fingerprint_digest",
        "candidate_repository_sha",
        "decision",
        "fulfilment",
        "transition",
        "transition_state",
        "baseline_changed",
        "persisted_selection",
        "persisted_selection_digest",
        "selection_persistence_authority",
        "automatic_replay_authority",
        "scheduler_authority",
        "workflow_dispatch_authority",
        "mutable_pointer_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
        "handoff_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationSelectedHandoffV1:
    """Self-contained receipt for one exact selected-baseline handoff."""

    source_selection: ReplayRevalidationBaselineSelectionV1
    candidate_fingerprint_digest: str
    candidate_repository_sha: str
    decision: ReplayRevalidationDecisionV1
    fulfilment: ReplayRevalidationFulfilmentV1
    transition: ReplayRevalidationBaselineTransitionV1
    persisted_selection: ReplayRevalidationBaselineSelectionV1
    schema: str = REVALIDATION_SELECTED_HANDOFF_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_SELECTED_HANDOFF_SCHEMA_V1:
            raise ReplayRevalidationSelectedHandoffError(
                f"unsupported handoff schema: {self.schema}"
            )
        try:
            source = ReplayRevalidationBaselineSelectionV1.from_dict(
                self.source_selection.canonical_dict()
            )
            persisted = ReplayRevalidationBaselineSelectionV1.from_dict(
                self.persisted_selection.canonical_dict()
            )
            verify_revalidation_baseline_selection_v1(source)
            verify_revalidation_baseline_selection_v1(persisted)
        except ReplayRevalidationBaselineSelectionError as exc:
            raise ReplayRevalidationSelectedHandoffError(
                f"invalid LRD-01R selection evidence: {exc}"
            ) from exc
        object.__setattr__(self, "source_selection", source)
        object.__setattr__(self, "persisted_selection", persisted)

        try:
            decision = ReplayRevalidationDecisionV1.from_dict(
                self.decision.canonical_dict()
            )
            fulfilment = ReplayRevalidationFulfilmentV1.from_dict(
                self.fulfilment.canonical_dict()
            )
            transition = ReplayRevalidationBaselineTransitionV1.from_dict(
                self.transition.canonical_dict()
            )
        except (ReplayRevalidationError, ReplayRevalidationFulfilmentError,
                ReplayRevalidationBaselineTransitionError) as exc:
            raise ReplayRevalidationSelectedHandoffError(
                f"invalid nested revalidation evidence: {exc}"
            ) from exc
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "fulfilment", fulfilment)
        object.__setattr__(self, "transition", transition)
        object.__setattr__(
            self,
            "candidate_fingerprint_digest",
            _digest(
                self.candidate_fingerprint_digest,
                field="candidate_fingerprint_digest",
            ),
        )
        object.__setattr__(
            self,
            "candidate_repository_sha",
            _git_sha(self.candidate_repository_sha, field="candidate_repository_sha"),
        )

        if decision.candidate_fingerprint_digest != self.candidate_fingerprint_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "decision/candidate fingerprint mismatch"
            )
        if fulfilment.decision_digest != decision.decision_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "fulfilment/decision digest mismatch"
            )
        if fulfilment.candidate_fingerprint_digest != self.candidate_fingerprint_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "fulfilment/candidate fingerprint mismatch"
            )
        if fulfilment.candidate_repository_sha != self.candidate_repository_sha:
            raise ReplayRevalidationSelectedHandoffError(
                "fulfilment/candidate repository SHA mismatch"
            )
        if transition.decision_digest != decision.decision_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "transition/decision digest mismatch"
            )
        if transition.fulfilment_digest != fulfilment.fulfilment_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "transition/fulfilment digest mismatch"
            )
        if transition.candidate_fingerprint_digest != self.candidate_fingerprint_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "transition/candidate fingerprint mismatch"
            )
        if transition.candidate_repository_sha != self.candidate_repository_sha:
            raise ReplayRevalidationSelectedHandoffError(
                "transition/candidate repository SHA mismatch"
            )
        if persisted.previous_selection_digest != source.selection_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "persisted selection does not descend from source selection"
            )
        source_lineage = source.lineage
        persisted_lineage = persisted.lineage
        if persisted_lineage.genesis_baseline != source_lineage.genesis_baseline:
            raise ReplayRevalidationSelectedHandoffError(
                "persisted lineage changed source genesis baseline"
            )
        if len(persisted_lineage.entries) != len(source_lineage.entries) + 1:
            raise ReplayRevalidationSelectedHandoffError(
                "handoff must extend selected lineage by exactly one entry"
            )
        if persisted_lineage.entries[:-1] != source_lineage.entries:
            raise ReplayRevalidationSelectedHandoffError(
                "persisted lineage is not an exact source-lineage extension"
            )
        if persisted_lineage.entries[-1].transition != transition:
            raise ReplayRevalidationSelectedHandoffError(
                "persisted lineage transition does not match handoff transition"
            )

    @property
    def source_selection_digest(self) -> str:
        return self.source_selection.selection_digest

    @property
    def transition_state(self) -> ReplayRevalidationBaselineTransitionState:
        return self.transition.state

    @property
    def baseline_changed(self) -> bool:
        return self.transition_state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED

    @property
    def persisted_selection_digest(self) -> str:
        return self.persisted_selection.selection_digest

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_selection": self.source_selection.canonical_dict(),
            "source_selection_digest": self.source_selection_digest,
            "candidate_fingerprint_digest": self.candidate_fingerprint_digest,
            "candidate_repository_sha": self.candidate_repository_sha,
            "decision": self.decision.canonical_dict(),
            "fulfilment": self.fulfilment.canonical_dict(),
            "transition": self.transition.canonical_dict(),
            "transition_state": self.transition_state.value,
            "baseline_changed": self.baseline_changed,
            "persisted_selection": self.persisted_selection.canonical_dict(),
            "persisted_selection_digest": self.persisted_selection_digest,
            "selection_persistence_authority": True,
            "automatic_replay_authority": False,
            "scheduler_authority": False,
            "workflow_dispatch_authority": False,
            "mutable_pointer_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
            "storage_authority": False,
            "provider_authority": False,
        }

    @property
    def handoff_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "handoff_digest": self.handoff_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationSelectedHandoffV1:
        _strict(value, _HANDOFF_KEYS, field="selected revalidation handoff")
        if value.get("selection_persistence_authority") is not True:
            raise ReplayRevalidationSelectedHandoffError(
                "selection_persistence_authority must remain true"
            )
        for authority in (
            "automatic_replay_authority",
            "scheduler_authority",
            "workflow_dispatch_authority",
            "mutable_pointer_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
            "storage_authority",
            "provider_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationSelectedHandoffError(
                    f"{authority} must remain false"
                )
        raw_source = value.get("source_selection")
        raw_decision = value.get("decision")
        raw_fulfilment = value.get("fulfilment")
        raw_transition = value.get("transition")
        raw_persisted = value.get("persisted_selection")
        if not all(
            isinstance(item, Mapping)
            for item in (
                raw_source,
                raw_decision,
                raw_fulfilment,
                raw_transition,
                raw_persisted,
            )
        ):
            raise ReplayRevalidationSelectedHandoffError(
                "nested handoff evidence must be objects"
            )
        assert isinstance(raw_source, Mapping)
        assert isinstance(raw_decision, Mapping)
        assert isinstance(raw_fulfilment, Mapping)
        assert isinstance(raw_transition, Mapping)
        assert isinstance(raw_persisted, Mapping)
        try:
            result = cls(
                schema=_text(value.get("schema"), field="schema"),
                source_selection=ReplayRevalidationBaselineSelectionV1.from_dict(
                    raw_source
                ),
                candidate_fingerprint_digest=_digest(
                    value.get("candidate_fingerprint_digest"),
                    field="candidate_fingerprint_digest",
                ),
                candidate_repository_sha=_git_sha(
                    value.get("candidate_repository_sha"),
                    field="candidate_repository_sha",
                ),
                decision=ReplayRevalidationDecisionV1.from_dict(raw_decision),
                fulfilment=ReplayRevalidationFulfilmentV1.from_dict(raw_fulfilment),
                transition=ReplayRevalidationBaselineTransitionV1.from_dict(
                    raw_transition
                ),
                persisted_selection=ReplayRevalidationBaselineSelectionV1.from_dict(
                    raw_persisted
                ),
            )
        except (
            ReplayRevalidationError,
            ReplayRevalidationFulfilmentError,
            ReplayRevalidationBaselineTransitionError,
            ReplayRevalidationBaselineSelectionError,
        ) as exc:
            raise ReplayRevalidationSelectedHandoffError(
                f"invalid nested handoff evidence: {exc}"
            ) from exc
        if value.get("source_selection_digest") != result.source_selection_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "source_selection_digest mismatch"
            )
        if value.get("transition_state") != result.transition_state.value:
            raise ReplayRevalidationSelectedHandoffError("transition_state mismatch")
        if value.get("baseline_changed") is not result.baseline_changed:
            raise ReplayRevalidationSelectedHandoffError("baseline_changed mismatch")
        if value.get("persisted_selection_digest") != result.persisted_selection_digest:
            raise ReplayRevalidationSelectedHandoffError(
                "persisted_selection_digest mismatch"
            )
        expected = _digest(value.get("handoff_digest"), field="handoff_digest")
        if expected != result.handoff_digest:
            raise ReplayRevalidationSelectedHandoffError("handoff_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationSelectedHandoffError(
                "selected revalidation handoff is not canonical"
            )
        return result


def _canonical_candidate(
    candidate: ReplayRevalidationFingerprintV1,
) -> ReplayRevalidationFingerprintV1:
    try:
        return ReplayRevalidationFingerprintV1.from_dict(candidate.canonical_dict())
    except (AttributeError, ReplayRevalidationError) as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"invalid candidate revalidation fingerprint: {exc}"
        ) from exc


def _evaluate_from_source(
    *,
    source: ReplayRevalidationBaselineSelectionV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None,
    replay_repository_sha: str | None,
) -> tuple[
    ReplayRevalidationDecisionV1,
    ReplayRevalidationFulfilmentV1,
    ReplayRevalidationBaselineTransitionV1,
    ReplayRevalidationBaselineLineageEntryV1,
]:
    try:
        verify_revalidation_baseline_selection_v1(source)
        prior_baseline = source.lineage.current_baseline
        baseline_fingerprint, baseline_runtime = prior_baseline.invalidation_inputs()
        decision = evaluate_revalidation_requirement_v1(
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime,
            candidate_runtime_identity=candidate_runtime_identity,
        )
        fulfilment = evaluate_revalidation_fulfilment_v1(
            decision=decision,
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_repository_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
        evaluation = evaluate_revalidation_baseline_transition_v1(
            prior_baseline=prior_baseline,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_repository_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
        entry = ReplayRevalidationBaselineLineageEntryV1(
            transition=evaluation.transition,
            resulting_baseline=evaluation.resulting_baseline,
        )
    except (
        ReplayRevalidationBaselineSelectionError,
        ReplayRevalidationError,
        ReplayRevalidationFulfilmentError,
        ReplayRevalidationBaselineTransitionError,
        ReplayRevalidationBaselineLineageError,
    ) as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"selected revalidation handoff evaluation failed: {exc}"
        ) from exc
    return decision, fulfilment, evaluation.transition, entry


def verify_selected_baseline_revalidation_handoff_v1(
    handoff: ReplayRevalidationSelectedHandoffV1,
    *,
    source_selection: ReplayRevalidationBaselineSelectionV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> str:
    """Purely recompute one handoff from exact source/candidate evidence."""
    canonical_candidate = _canonical_candidate(candidate)
    try:
        canonical_source = ReplayRevalidationBaselineSelectionV1.from_dict(
            source_selection.canonical_dict()
        )
    except (AttributeError, ReplayRevalidationBaselineSelectionError) as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"invalid source selection: {exc}"
        ) from exc
    if handoff.source_selection != canonical_source:
        raise ReplayRevalidationSelectedHandoffError(
            "handoff source selection evidence mismatch"
        )
    candidate_sha = _git_sha(
        candidate_repository_sha,
        field="candidate_repository_sha",
    )
    decision, fulfilment, transition, entry = _evaluate_from_source(
        source=canonical_source,
        candidate=canonical_candidate,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )
    try:
        expected_lineage = canonical_source.lineage.append(entry)
        expected_persisted = ReplayRevalidationBaselineSelectionV1(
            lineage=expected_lineage,
            previous_selection_digest=canonical_source.selection_digest,
        )
    except (
        ReplayRevalidationBaselineLineageError,
        ReplayRevalidationBaselineSelectionError,
    ) as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"expected handoff lineage is invalid: {exc}"
        ) from exc
    expected = ReplayRevalidationSelectedHandoffV1(
        source_selection=canonical_source,
        candidate_fingerprint_digest=canonical_candidate.fingerprint_digest,
        candidate_repository_sha=candidate_sha,
        decision=decision,
        fulfilment=fulfilment,
        transition=transition,
        persisted_selection=expected_persisted,
    )
    if handoff.canonical_dict() != expected.canonical_dict():
        raise ReplayRevalidationSelectedHandoffError(
            "selected revalidation handoff evidence mismatch"
        )
    return handoff.handoff_digest


def execute_selected_baseline_revalidation_handoff_v1(
    *,
    ledger: ReplayRevalidationBaselineSelectionLedgerV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> ReplayRevalidationSelectedHandoffV1:
    """Execute one caller-invoked fail-closed handoff through existing LRD authorities."""
    if not isinstance(ledger, ReplayRevalidationBaselineSelectionLedgerV1):
        raise ReplayRevalidationSelectedHandoffError(
            "handoff requires ReplayRevalidationBaselineSelectionLedgerV1"
        )
    canonical_candidate = _canonical_candidate(candidate)
    candidate_sha = _git_sha(
        candidate_repository_sha,
        field="candidate_repository_sha",
    )
    try:
        source = ledger.current_selection()
    except ReplayRevalidationBaselineSelectionError as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"cannot verify current selected baseline: {exc}"
        ) from exc
    if source is None:
        raise ReplayRevalidationSelectedHandoffError(
            "current selected baseline is missing; explicit LRD-01R bootstrap is required"
        )
    decision, fulfilment, transition, entry = _evaluate_from_source(
        source=source,
        candidate=canonical_candidate,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )
    try:
        next_lineage = source.lineage.append(entry)
        persisted = ledger.append(next_lineage)
    except (
        ReplayRevalidationBaselineLineageError,
        ReplayRevalidationBaselineSelectionError,
    ) as exc:
        raise ReplayRevalidationSelectedHandoffError(
            f"selected lineage compare-and-append failed: {exc}"
        ) from exc
    handoff = ReplayRevalidationSelectedHandoffV1(
        source_selection=source,
        candidate_fingerprint_digest=canonical_candidate.fingerprint_digest,
        candidate_repository_sha=candidate_sha,
        decision=decision,
        fulfilment=fulfilment,
        transition=transition,
        persisted_selection=persisted,
    )
    verify_selected_baseline_revalidation_handoff_v1(
        handoff,
        source_selection=source,
        candidate=canonical_candidate,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )
    return handoff
