"""Operational exactly-once logical external-action coordination.

The coordinator is deliberately operational state, not CASE-history authority.
Every material reservation/outcome still has to be written to CanonicalCaseLedger
by the caller.  Its purpose is to make duplicate/concurrent invocations fail safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import RLock

from core.case_product_hardening_v1 import (
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ExternalActionState,
    IdempotencyConflictError,
    verify_receipt_for_transition,
)


class ReservationDisposition(StrEnum):
    INVOKE_ALLOWED = "INVOKE_ALLOWED"
    IN_PROGRESS = "IN_PROGRESS"
    REPLAY_CONFIRMED = "REPLAY_CONFIRMED"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"


@dataclass(slots=True)
class CoordinatedAction:
    identity: ExternalActionIdentity
    state: ExternalActionState
    owner_attempt_id: str
    attempt_count: int = 1
    receipt: ExternalActionReceipt | None = None


@dataclass(frozen=True, slots=True)
class ReservationResult:
    disposition: ReservationDisposition
    record: CoordinatedAction

    @property
    def invoke_allowed(self) -> bool:
        return self.disposition is ReservationDisposition.INVOKE_ALLOWED


class SafeExternalActionCoordinator:
    """Thread-safe in-process reference semantics for logical action execution."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, CoordinatedAction] = {}
        self._logical_keys: dict[tuple[str, str], str] = {}

    def reserve(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> ReservationResult:
        if not attempt_id or attempt_id != attempt_id.strip():
            raise CaseProductHardeningError("attempt_id must be nonblank and canonical")
        key = identity.idempotency_key
        logical = (identity.case_id.value, identity.logical_action_id)
        with self._lock:
            prior_key = self._logical_keys.get(logical)
            if prior_key is not None and prior_key != key:
                raise IdempotencyConflictError(
                    "logical action id cannot be reused for a different immutable intent"
                )
            existing = self._records.get(key)
            if existing is None:
                record = CoordinatedAction(
                    identity=identity,
                    state=ExternalActionState.RESERVED,
                    owner_attempt_id=attempt_id,
                )
                self._records[key] = record
                self._logical_keys[logical] = key
                return ReservationResult(ReservationDisposition.INVOKE_ALLOWED, record)

            if existing.state in {
                ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
                ExternalActionState.RECEIPT_RECOVERED,
            }:
                return ReservationResult(ReservationDisposition.REPLAY_CONFIRMED, existing)
            if existing.state is ExternalActionState.OUTCOME_UNKNOWN:
                return ReservationResult(ReservationDisposition.RECONCILE_REQUIRED, existing)
            if existing.state is ExternalActionState.RESERVED:
                return ReservationResult(ReservationDisposition.IN_PROGRESS, existing)
            if existing.state in {
                ExternalActionState.PRE_EFFECT_FAILED,
                ExternalActionState.CONFIRMED_NO_EFFECT,
            }:
                existing.state = ExternalActionState.RESERVED
                existing.owner_attempt_id = attempt_id
                existing.attempt_count += 1
                existing.receipt = None
                return ReservationResult(ReservationDisposition.INVOKE_ALLOWED, existing)
            raise CaseProductHardeningError("unsupported external action state")

    def mark_pre_effect_failed(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> CoordinatedAction:
        with self._lock:
            record = self._owned(identity, attempt_id=attempt_id)
            record.state = ExternalActionState.PRE_EFFECT_FAILED
            return record

    def mark_outcome_unknown(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> CoordinatedAction:
        with self._lock:
            record = self._owned(identity, attempt_id=attempt_id)
            record.state = ExternalActionState.OUTCOME_UNKNOWN
            return record

    def confirm_no_effect(
        self,
        identity: ExternalActionIdentity,
        *,
        reconciliation_ref: str,
    ) -> CoordinatedAction:
        if not reconciliation_ref or reconciliation_ref != reconciliation_ref.strip():
            raise CaseProductHardeningError("reconciliation_ref must be nonblank and canonical")
        with self._lock:
            record = self._require(identity)
            if record.state is not ExternalActionState.OUTCOME_UNKNOWN:
                raise CaseProductHardeningError(
                    "confirmed no-effect reconciliation requires OUTCOME_UNKNOWN"
                )
            record.state = ExternalActionState.CONFIRMED_NO_EFFECT
            return record

    def confirm_success(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        receipt: ExternalActionReceipt,
    ) -> CoordinatedAction:
        verify_receipt_for_transition(receipt, identity)
        with self._lock:
            record = self._owned(identity, attempt_id=attempt_id)
            record.state = ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS
            record.receipt = receipt
            return record

    def recover_receipt(
        self,
        identity: ExternalActionIdentity,
        *,
        receipt: ExternalActionReceipt,
        reconciliation_ref: str,
    ) -> CoordinatedAction:
        verify_receipt_for_transition(receipt, identity)
        if not reconciliation_ref or reconciliation_ref != reconciliation_ref.strip():
            raise CaseProductHardeningError("reconciliation_ref must be nonblank and canonical")
        with self._lock:
            record = self._require(identity)
            if record.state is not ExternalActionState.OUTCOME_UNKNOWN:
                raise CaseProductHardeningError("receipt recovery requires OUTCOME_UNKNOWN")
            record.state = ExternalActionState.RECEIPT_RECOVERED
            record.receipt = receipt
            return record

    def _require(self, identity: ExternalActionIdentity) -> CoordinatedAction:
        record = self._records.get(identity.idempotency_key)
        if record is None:
            raise CaseProductHardeningError("external action has no reservation")
        return record

    def _owned(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> CoordinatedAction:
        record = self._require(identity)
        if record.state is not ExternalActionState.RESERVED:
            raise CaseProductHardeningError("external action is not in an invokable reservation")
        if record.owner_attempt_id != attempt_id:
            raise CaseProductHardeningError("attempt does not own the active reservation")
        return record


__all__ = [
    "CoordinatedAction",
    "ReservationDisposition",
    "ReservationResult",
    "SafeExternalActionCoordinator",
]
