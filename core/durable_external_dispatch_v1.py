"""Crash-safe external-provider dispatch on top of durable action coordination.

The dispatch fence is operational state, not CASE-history authority. Material CASE
facts and lifecycle events still belong in CanonicalCaseLedger. The fence exists to
close the crash window between granting invoke permission and learning the provider
outcome: once dispatch begins, a restart must reconcile instead of blindly retrying.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from core.case_ledger import ContentAddress
from core.case_product_hardening_v1 import (
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ExternalActionState,
)
from core.durable_external_action_v1 import DurableExternalActionCoordinator
from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import DurableRecord, SQLiteProvenanceStore
from core.external_action_execution_v1 import (
    ReservationDisposition,
    ReservationResult,
)

DURABLE_DISPATCH_FENCE_SCHEMA_V1 = "lukart.durable-dispatch-fence.v1"
_DISPATCH_STARTED = "external-action.dispatch-started.v1"
_DISPATCH_RESOLVED = "external-action.dispatch-resolved.v1"
_GENESIS = "0" * 64


class DispatchResolution(StrEnum):
    SUCCESS = "SUCCESS"
    NO_EFFECT = "NO_EFFECT"


@dataclass(frozen=True, slots=True)
class DispatchFenceSnapshot:
    identity_digest: ContentAddress
    attempt_id: str
    dispatch_ref: str
    started_at: datetime
    resolution: DispatchResolution | None = None
    resolution_evidence_ref: str | None = None
    resolved_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.resolution is None


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CaseProductHardeningError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CaseProductHardeningError(f"{field_name} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise CaseProductHardeningError(f"{field_name} keys must be strings")
    return cast(Mapping[str, object], value)


def _aware_datetime(value: object, *, field_name: str) -> datetime:
    raw = _text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CaseProductHardeningError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CaseProductHardeningError(f"{field_name} must be timezone-aware")
    return parsed


def _dispatch_stream_id(identity: ExternalActionIdentity, attempt_id: str) -> str:
    digest = ContentAddress.for_value(
        {
            "identity_digest": identity.identity_digest.digest,
            "attempt_id": attempt_id,
        }
    )
    return f"external-dispatch:{digest.digest}"


class DurableExternalActionExecutor:
    """Persist a dispatch fence before any external-provider invocation.

    The caller must route provider invocation through :meth:`execute` or explicitly
    call :meth:`begin_dispatch` before invoking the provider. After a dispatch fence
    exists, a restart returns RECONCILE_REQUIRED until success or confirmed no-effect
    is established.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._actions = DurableExternalActionCoordinator(self.path)
        self._store = SQLiteProvenanceStore(self.path)

    def close(self) -> None:
        self._actions.close()
        self._store.close()

    def __enter__(self) -> DurableExternalActionExecutor:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _dispatch_records(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> tuple[DurableRecord, ...]:
        stream_id = _dispatch_stream_id(identity, attempt_id)
        try:
            verified = self._store.verify()
        except EnterpriseContractError as exc:
            raise CaseProductHardeningError(
                "durable dispatch backend verification failed"
            ) from exc
        return tuple(record for record in verified if record.stream_id == stream_id)

    def dispatch_fence(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> DispatchFenceSnapshot | None:
        attempt = _text(attempt_id, field_name="attempt_id")
        records = self._dispatch_records(identity, attempt_id=attempt)
        if not records:
            return None
        if len(records) > 2:
            raise CaseProductHardeningError("dispatch fence contains excess transitions")
        first = records[0]
        if first.event_type != _DISPATCH_STARTED:
            raise CaseProductHardeningError("dispatch stream must start with DISPATCH_STARTED")
        start_payload = _mapping(first.payload, field_name="dispatch start payload")
        if start_payload.get("schema") != DURABLE_DISPATCH_FENCE_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported dispatch fence schema")
        if start_payload.get("identity_digest") != identity.identity_digest.digest:
            raise CaseProductHardeningError("dispatch fence identity mismatch")
        stored_attempt = _text(start_payload.get("attempt_id"), field_name="attempt_id")
        if stored_attempt != attempt:
            raise CaseProductHardeningError("dispatch fence attempt mismatch")
        dispatch_ref = _text(start_payload.get("dispatch_ref"), field_name="dispatch_ref")
        started_at = _aware_datetime(
            start_payload.get("started_at"),
            field_name="dispatch started_at",
        )
        if len(records) == 1:
            return DispatchFenceSnapshot(
                identity_digest=identity.identity_digest,
                attempt_id=attempt,
                dispatch_ref=dispatch_ref,
                started_at=started_at,
            )

        resolved = records[1]
        if resolved.event_type != _DISPATCH_RESOLVED:
            raise CaseProductHardeningError("invalid dispatch fence terminal event")
        resolution_payload = _mapping(
            resolved.payload,
            field_name="dispatch resolution payload",
        )
        if resolution_payload.get("schema") != DURABLE_DISPATCH_FENCE_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported dispatch resolution schema")
        if resolution_payload.get("identity_digest") != identity.identity_digest.digest:
            raise CaseProductHardeningError("dispatch resolution identity mismatch")
        if resolution_payload.get("attempt_id") != attempt:
            raise CaseProductHardeningError("dispatch resolution attempt mismatch")
        try:
            resolution = DispatchResolution(
                _text(
                    resolution_payload.get("resolution"),
                    field_name="dispatch resolution",
                )
            )
        except ValueError as exc:
            raise CaseProductHardeningError("unsupported dispatch resolution") from exc
        evidence_ref = _text(
            resolution_payload.get("evidence_ref"),
            field_name="dispatch resolution evidence_ref",
        )
        resolved_at = _aware_datetime(
            resolution_payload.get("resolved_at"),
            field_name="dispatch resolved_at",
        )
        return DispatchFenceSnapshot(
            identity_digest=identity.identity_digest,
            attempt_id=attempt,
            dispatch_ref=dispatch_ref,
            started_at=started_at,
            resolution=resolution,
            resolution_evidence_ref=evidence_ref,
            resolved_at=resolved_at,
        )

    def reserve(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> ReservationResult:
        result = self._actions.reserve(identity, attempt_id=attempt_id)
        if result.disposition is ReservationDisposition.IN_PROGRESS:
            owner_attempt = result.record.owner_attempt_id
            fence = self.dispatch_fence(identity, attempt_id=owner_attempt)
            if fence is not None and fence.active:
                return ReservationResult(
                    ReservationDisposition.RECONCILE_REQUIRED,
                    result.record,
                )
        return result

    def begin_dispatch(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        dispatch_ref: str,
        started_at: datetime | None = None,
    ) -> DispatchFenceSnapshot:
        attempt = _text(attempt_id, field_name="attempt_id")
        operation_ref = _text(dispatch_ref, field_name="dispatch_ref")
        existing = self.dispatch_fence(identity, attempt_id=attempt)
        if existing is not None:
            if existing.dispatch_ref != operation_ref:
                raise CaseProductHardeningError(
                    "dispatch attempt already has a different dispatch_ref"
                )
            if not existing.active:
                raise CaseProductHardeningError("resolved dispatch cannot be started again")
            return existing

        reservation = self._actions.reserve(identity, attempt_id=attempt)
        if reservation.record.owner_attempt_id != attempt:
            raise CaseProductHardeningError("attempt does not own the active reservation")
        if reservation.record.state is not ExternalActionState.RESERVED:
            raise CaseProductHardeningError("external action is not dispatchable")
        if reservation.disposition not in {
            ReservationDisposition.IN_PROGRESS,
            ReservationDisposition.INVOKE_ALLOWED,
        }:
            raise CaseProductHardeningError("external action is not dispatchable")

        moment = started_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise CaseProductHardeningError("dispatch started_at must be timezone-aware")
        payload = {
            "schema": DURABLE_DISPATCH_FENCE_SCHEMA_V1,
            "identity_digest": identity.identity_digest.digest,
            "attempt_id": attempt,
            "dispatch_ref": operation_ref,
            "started_at": moment.isoformat(),
        }
        try:
            self._store.append(
                stream_id=_dispatch_stream_id(identity, attempt),
                event_type=_DISPATCH_STARTED,
                payload=payload,
                expected_stream_head=_GENESIS,
            )
        except EnterpriseContractError as exc:
            winner = self.dispatch_fence(identity, attempt_id=attempt)
            if winner is None:
                raise CaseProductHardeningError(
                    "dispatch fence could not be persisted"
                ) from exc
            if winner.dispatch_ref != operation_ref:
                raise CaseProductHardeningError(
                    "concurrent dispatch used a conflicting dispatch_ref"
                ) from exc
            return winner
        persisted = self.dispatch_fence(identity, attempt_id=attempt)
        if persisted is None or not persisted.active:
            raise CaseProductHardeningError("dispatch fence persistence verification failed")
        return persisted

    def _resolve_dispatch(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        resolution: DispatchResolution,
        evidence_ref: str,
        resolved_at: datetime | None = None,
    ) -> DispatchFenceSnapshot:
        attempt = _text(attempt_id, field_name="attempt_id")
        evidence = _text(evidence_ref, field_name="dispatch resolution evidence_ref")
        fence = self.dispatch_fence(identity, attempt_id=attempt)
        if fence is None:
            raise CaseProductHardeningError("dispatch was never started")
        if not fence.active:
            if fence.resolution is resolution and fence.resolution_evidence_ref == evidence:
                return fence
            raise CaseProductHardeningError("dispatch already has a different resolution")
        moment = resolved_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise CaseProductHardeningError("dispatch resolved_at must be timezone-aware")
        records = self._dispatch_records(identity, attempt_id=attempt)
        if len(records) != 1:
            raise CaseProductHardeningError("dispatch fence changed during resolution")
        payload = {
            "schema": DURABLE_DISPATCH_FENCE_SCHEMA_V1,
            "identity_digest": identity.identity_digest.digest,
            "attempt_id": attempt,
            "resolution": resolution.value,
            "evidence_ref": evidence,
            "resolved_at": moment.isoformat(),
        }
        try:
            self._store.append(
                stream_id=_dispatch_stream_id(identity, attempt),
                event_type=_DISPATCH_RESOLVED,
                payload=payload,
                expected_stream_head=records[-1].record_digest,
            )
        except EnterpriseContractError as exc:
            raise CaseProductHardeningError(
                "dispatch fence changed during resolution"
            ) from exc
        resolved = self.dispatch_fence(identity, attempt_id=attempt)
        if resolved is None or resolved.active:
            raise CaseProductHardeningError("dispatch resolution verification failed")
        return resolved

    def mark_pre_effect_failed(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> None:
        fence = self.dispatch_fence(identity, attempt_id=attempt_id)
        if fence is not None:
            raise CaseProductHardeningError(
                "pre-effect failure cannot be asserted after dispatch started"
            )
        self._actions.mark_pre_effect_failed(identity, attempt_id=attempt_id)

    def mark_outcome_unknown(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> None:
        fence = self.dispatch_fence(identity, attempt_id=attempt_id)
        if fence is None or not fence.active:
            raise CaseProductHardeningError(
                "OUTCOME_UNKNOWN requires an active dispatch fence"
            )
        current = self._actions.reserve(identity, attempt_id=attempt_id)
        if current.record.state is ExternalActionState.RESERVED:
            self._actions.mark_outcome_unknown(identity, attempt_id=attempt_id)
        elif current.record.state is not ExternalActionState.OUTCOME_UNKNOWN:
            raise CaseProductHardeningError(
                "external action cannot transition to OUTCOME_UNKNOWN"
            )

    def confirm_success(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        receipt: ExternalActionReceipt,
    ) -> ExternalActionReceipt:
        attempt = _text(attempt_id, field_name="attempt_id")
        fence = self.dispatch_fence(identity, attempt_id=attempt)
        if fence is None or not fence.active:
            raise CaseProductHardeningError("confirmed success requires active dispatch")
        if receipt.attempt_id != attempt:
            raise CaseProductHardeningError("receipt attempt does not match dispatch attempt")
        record = self._actions.confirm_success(
            identity,
            attempt_id=attempt,
            receipt=receipt,
        )
        self._resolve_dispatch(
            identity,
            attempt_id=attempt,
            resolution=DispatchResolution.SUCCESS,
            evidence_ref=receipt.receipt_id,
        )
        if record.receipt is None:
            raise CaseProductHardeningError("confirmed success lost its receipt")
        return record.receipt

    def recover_receipt(
        self,
        identity: ExternalActionIdentity,
        *,
        receipt: ExternalActionReceipt,
        reconciliation_ref: str,
    ) -> ExternalActionReceipt:
        result = self.reserve(identity, attempt_id=receipt.attempt_id)
        if result.disposition is ReservationDisposition.REPLAY_CONFIRMED:
            if result.record.receipt != receipt:
                raise CaseProductHardeningError(
                    "external action already has a different confirmed receipt"
                )
            return receipt
        fence = self.dispatch_fence(identity, attempt_id=result.record.owner_attempt_id)
        if fence is None or not fence.active:
            raise CaseProductHardeningError("receipt recovery requires active dispatch")
        if receipt.attempt_id != result.record.owner_attempt_id:
            raise CaseProductHardeningError("receipt attempt does not match active dispatch")
        if result.record.state is ExternalActionState.RESERVED:
            self._actions.mark_outcome_unknown(
                identity,
                attempt_id=result.record.owner_attempt_id,
            )
        recovered = self._actions.recover_receipt(
            identity,
            receipt=receipt,
            reconciliation_ref=reconciliation_ref,
        )
        self._resolve_dispatch(
            identity,
            attempt_id=result.record.owner_attempt_id,
            resolution=DispatchResolution.SUCCESS,
            evidence_ref=reconciliation_ref,
        )
        if recovered.receipt is None:
            raise CaseProductHardeningError("receipt recovery lost its receipt")
        return recovered.receipt

    def confirm_no_effect(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        reconciliation_ref: str,
    ) -> None:
        attempt = _text(attempt_id, field_name="attempt_id")
        fence = self.dispatch_fence(identity, attempt_id=attempt)
        if fence is None or not fence.active:
            raise CaseProductHardeningError(
                "confirmed no-effect requires active dispatch"
            )
        current = self._actions.reserve(identity, attempt_id=attempt)
        if current.record.owner_attempt_id != attempt:
            raise CaseProductHardeningError("attempt does not own active dispatch")
        if current.record.state is ExternalActionState.RESERVED:
            self._actions.mark_outcome_unknown(identity, attempt_id=attempt)
        self._actions.confirm_no_effect(
            identity,
            reconciliation_ref=reconciliation_ref,
        )
        self._resolve_dispatch(
            identity,
            attempt_id=attempt,
            resolution=DispatchResolution.NO_EFFECT,
            evidence_ref=reconciliation_ref,
        )

    def execute(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        dispatch_ref: str,
        provider_call: Callable[[], ExternalActionReceipt],
    ) -> ExternalActionReceipt:
        reservation = self.reserve(identity, attempt_id=attempt_id)
        if reservation.disposition is ReservationDisposition.REPLAY_CONFIRMED:
            if reservation.record.receipt is None:
                raise CaseProductHardeningError("confirmed replay is missing receipt")
            return reservation.record.receipt
        if reservation.disposition is not ReservationDisposition.INVOKE_ALLOWED:
            raise CaseProductHardeningError(
                f"provider invocation forbidden: {reservation.disposition.value}"
            )
        self.begin_dispatch(
            identity,
            attempt_id=attempt_id,
            dispatch_ref=dispatch_ref,
        )
        try:
            receipt = provider_call()
        except BaseException:
            self.mark_outcome_unknown(identity, attempt_id=attempt_id)
            raise
        return self.confirm_success(
            identity,
            attempt_id=attempt_id,
            receipt=receipt,
        )


__all__ = [
    "DURABLE_DISPATCH_FENCE_SCHEMA_V1",
    "DispatchFenceSnapshot",
    "DispatchResolution",
    "DurableExternalActionExecutor",
]
