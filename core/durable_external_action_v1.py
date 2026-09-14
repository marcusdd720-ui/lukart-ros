"""Durable exactly-once logical external-action coordination.

This module persists operational reservation/reconciliation state across process
restarts and competing workers. It is deliberately *not* CASE-history authority:
material CASE events still belong in CanonicalCaseLedger. The existing
SQLiteProvenanceStore is reused as an append-only operational compare-and-append
backend so no competing CASE ledger is introduced.

Provider invocation is fenced in the same logical-action stream. A caller must
persist DISPATCHED before invoking the provider; from that point the action is
OUTCOME_UNKNOWN until a receipt or confirmed no-effect reconciliation resolves it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from core.case_ledger import CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ExternalActionState,
    IdempotencyConflictError,
    ReceiptOutcome,
    verify_receipt_for_transition,
)
from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import DurableRecord, SQLiteProvenanceStore
from core.external_action_execution_v1 import (
    CoordinatedAction,
    ReservationDisposition,
    ReservationResult,
)

DURABLE_EXTERNAL_ACTION_SCHEMA_V1 = "lukart.durable-external-action.v1"
_RESERVED = "external-action.reserved.v1"
_DISPATCHED = "external-action.dispatched.v1"
_PRE_EFFECT_FAILED = "external-action.pre-effect-failed.v1"
_OUTCOME_UNKNOWN = "external-action.outcome-unknown.v1"
_CONFIRMED_SUCCESS = "external-action.confirmed-success.v1"
_CONFIRMED_NO_EFFECT = "external-action.confirmed-no-effect.v1"
_RECEIPT_RECOVERED = "external-action.receipt-recovered.v1"
_GENESIS = "0" * 64
_MAX_TRANSITIONS = 1_000


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


def _content_address(value: object, *, field_name: str) -> ContentAddress:
    try:
        return ContentAddress.from_dict(_mapping(value, field_name=field_name))
    except ValueError as exc:
        raise CaseProductHardeningError(f"invalid {field_name}") from exc


def _identity_from_dict(value: Mapping[str, object]) -> ExternalActionIdentity:
    schema = _text(value.get("schema"), field_name="external action identity schema")
    payload_digest_raw = value.get("payload_digest")
    return ExternalActionIdentity(
        case_id=CaseId(_text(value.get("case_id"), field_name="case_id")),
        artifact_id=ObjectId(_text(value.get("artifact_id"), field_name="artifact_id")),
        artifact_version=_text(
            value.get("artifact_version"), field_name="artifact_version"
        ),
        artifact_digest=_content_address(
            value.get("artifact_digest"), field_name="artifact_digest"
        ),
        logical_action_id=_text(
            value.get("logical_action_id"), field_name="logical_action_id"
        ),
        action_type=_text(value.get("action_type"), field_name="action_type"),
        channel=_text(value.get("channel"), field_name="channel"),
        payload_digest=(
            None
            if payload_digest_raw is None
            else _content_address(payload_digest_raw, field_name="payload_digest")
        ),
        schema=schema,
    )


def _receipt_from_dict(value: Mapping[str, object]) -> ExternalActionReceipt:
    provider_reference_raw = value.get("provider_reference")
    external_timestamp_raw = value.get("external_timestamp")
    try:
        outcome = ReceiptOutcome(_text(value.get("outcome"), field_name="receipt outcome"))
    except ValueError as exc:
        raise CaseProductHardeningError("unsupported receipt outcome") from exc
    return ExternalActionReceipt(
        receipt_id=_text(value.get("receipt_id"), field_name="receipt_id"),
        identity_digest=_content_address(
            value.get("identity_digest"), field_name="receipt identity_digest"
        ),
        attempt_id=_text(value.get("attempt_id"), field_name="receipt attempt_id"),
        outcome=outcome,
        evidence_ref=_text(value.get("evidence_ref"), field_name="receipt evidence_ref"),
        provider_reference=(
            None
            if provider_reference_raw is None
            else _text(provider_reference_raw, field_name="provider_reference")
        ),
        external_timestamp=(
            None
            if external_timestamp_raw is None
            else _aware_datetime(
                external_timestamp_raw,
                field_name="receipt external_timestamp",
            )
        ),
        recorded_at=_aware_datetime(
            value.get("recorded_at"), field_name="receipt recorded_at"
        ),
        receipt_digest=_content_address(
            value.get("receipt_digest"), field_name="receipt_digest"
        ),
        schema_version=_text(
            value.get("schema_version"), field_name="receipt schema_version"
        ),
        schema=_text(value.get("schema"), field_name="receipt schema"),
    )


def _stream_id(identity: ExternalActionIdentity) -> str:
    logical_scope = ContentAddress.for_value(
        {
            "case_id": identity.case_id.value,
            "logical_action_id": identity.logical_action_id,
        }
    )
    return f"external-action:{logical_scope.digest}"


class DurableExternalActionCoordinator:
    """Cross-restart, multi-worker operational external-action coordinator."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._store = SQLiteProvenanceStore(self.path)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> DurableExternalActionCoordinator:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _records(self, identity: ExternalActionIdentity) -> tuple[DurableRecord, ...]:
        stream_id = _stream_id(identity)
        try:
            verified = self._store.verify()
        except EnterpriseContractError as exc:
            raise CaseProductHardeningError(
                "durable external-action backend verification failed"
            ) from exc
        matching = tuple(record for record in verified if record.stream_id == stream_id)
        if len(matching) > _MAX_TRANSITIONS:
            raise CaseProductHardeningError(
                "durable external-action transition limit exceeded"
            )
        return matching

    def _load(
        self,
        identity: ExternalActionIdentity,
    ) -> tuple[CoordinatedAction | None, str]:
        records = self._records(identity)
        if not records:
            return None, _GENESIS
        first = records[0]
        if first.event_type != _RESERVED:
            raise CaseProductHardeningError(
                "durable external-action stream must start with reservation"
            )
        first_payload = _mapping(first.payload, field_name="reservation payload")
        stored_identity = _identity_from_dict(
            _mapping(first_payload.get("identity"), field_name="stored identity")
        )
        if stored_identity.identity_digest != identity.identity_digest:
            raise IdempotencyConflictError(
                "logical action id cannot be reused for a different immutable intent"
            )

        state = ExternalActionState.RESERVED
        owner_attempt_id = _text(
            first_payload.get("attempt_id"), field_name="reservation attempt_id"
        )
        attempt_count = 1
        receipt: ExternalActionReceipt | None = None

        for index, record in enumerate(records):
            payload = _mapping(record.payload, field_name="external-action transition payload")
            if payload.get("schema") != DURABLE_EXTERNAL_ACTION_SCHEMA_V1:
                raise CaseProductHardeningError(
                    "unsupported durable external-action transition schema"
                )
            if payload.get("identity_digest") != identity.identity_digest.digest:
                raise CaseProductHardeningError(
                    "durable external-action transition identity mismatch"
                )
            if index == 0:
                continue
            if record.event_type == _RESERVED:
                if state not in {
                    ExternalActionState.PRE_EFFECT_FAILED,
                    ExternalActionState.CONFIRMED_NO_EFFECT,
                }:
                    raise CaseProductHardeningError(
                        "invalid durable external-action retry transition"
                    )
                state = ExternalActionState.RESERVED
                owner_attempt_id = _text(
                    payload.get("attempt_id"), field_name="reservation attempt_id"
                )
                attempt_count += 1
                receipt = None
            elif record.event_type == _DISPATCHED:
                if state is not ExternalActionState.RESERVED:
                    raise CaseProductHardeningError("invalid DISPATCHED transition")
                dispatch_attempt = _text(
                    payload.get("attempt_id"), field_name="dispatch attempt_id"
                )
                if dispatch_attempt != owner_attempt_id:
                    raise CaseProductHardeningError("dispatch attempt owner mismatch")
                _text(payload.get("dispatch_ref"), field_name="dispatch_ref")
                _aware_datetime(
                    payload.get("started_at"),
                    field_name="dispatch started_at",
                )
                state = ExternalActionState.OUTCOME_UNKNOWN
            elif record.event_type == _PRE_EFFECT_FAILED:
                if state is not ExternalActionState.RESERVED:
                    raise CaseProductHardeningError(
                        "invalid PRE_EFFECT_FAILED transition"
                    )
                state = ExternalActionState.PRE_EFFECT_FAILED
            elif record.event_type == _OUTCOME_UNKNOWN:
                if state is not ExternalActionState.RESERVED:
                    raise CaseProductHardeningError("invalid OUTCOME_UNKNOWN transition")
                state = ExternalActionState.OUTCOME_UNKNOWN
            elif record.event_type == _CONFIRMED_SUCCESS:
                if state is not ExternalActionState.OUTCOME_UNKNOWN:
                    raise CaseProductHardeningError(
                        "confirmed success requires a dispatched/unknown outcome"
                    )
                receipt = _receipt_from_dict(
                    _mapping(payload.get("receipt"), field_name="confirmed receipt")
                )
                if receipt.attempt_id != owner_attempt_id:
                    raise CaseProductHardeningError("confirmed receipt attempt mismatch")
                verify_receipt_for_transition(receipt, stored_identity)
                state = ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS
            elif record.event_type == _CONFIRMED_NO_EFFECT:
                if state is not ExternalActionState.OUTCOME_UNKNOWN:
                    raise CaseProductHardeningError(
                        "invalid CONFIRMED_NO_EFFECT transition"
                    )
                _text(
                    payload.get("reconciliation_ref"),
                    field_name="reconciliation_ref",
                )
                state = ExternalActionState.CONFIRMED_NO_EFFECT
            elif record.event_type == _RECEIPT_RECOVERED:
                if state is not ExternalActionState.OUTCOME_UNKNOWN:
                    raise CaseProductHardeningError(
                        "invalid RECEIPT_RECOVERED transition"
                    )
                _text(
                    payload.get("reconciliation_ref"),
                    field_name="reconciliation_ref",
                )
                receipt = _receipt_from_dict(
                    _mapping(payload.get("receipt"), field_name="recovered receipt")
                )
                if receipt.attempt_id != owner_attempt_id:
                    raise CaseProductHardeningError("recovered receipt attempt mismatch")
                verify_receipt_for_transition(receipt, stored_identity)
                state = ExternalActionState.RECEIPT_RECOVERED
            else:
                raise CaseProductHardeningError(
                    f"unsupported durable external-action event: {record.event_type}"
                )

        return (
            CoordinatedAction(
                identity=stored_identity,
                state=state,
                owner_attempt_id=owner_attempt_id,
                attempt_count=attempt_count,
                receipt=receipt,
            ),
            records[-1].record_digest,
        )

    def _append(
        self,
        identity: ExternalActionIdentity,
        *,
        event_type: str,
        payload: Mapping[str, object],
        expected_head: str,
    ) -> None:
        body = {
            "schema": DURABLE_EXTERNAL_ACTION_SCHEMA_V1,
            "identity_digest": identity.identity_digest.digest,
            **dict(payload),
        }
        self._store.append(
            stream_id=_stream_id(identity),
            event_type=event_type,
            payload=body,
            expected_stream_head=expected_head,
        )

    @staticmethod
    def _validate_attempt_id(attempt_id: str) -> str:
        return _text(attempt_id, field_name="attempt_id")

    def reserve(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> ReservationResult:
        attempt = self._validate_attempt_id(attempt_id)
        for _retry in range(4):
            current, head = self._load(identity)
            if current is None:
                payload: dict[str, object] = {
                    "identity": identity.canonical_dict(),
                    "attempt_id": attempt,
                }
            elif current.state in {
                ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
                ExternalActionState.RECEIPT_RECOVERED,
            }:
                return ReservationResult(ReservationDisposition.REPLAY_CONFIRMED, current)
            elif current.state is ExternalActionState.OUTCOME_UNKNOWN:
                return ReservationResult(ReservationDisposition.RECONCILE_REQUIRED, current)
            elif current.state is ExternalActionState.RESERVED:
                return ReservationResult(ReservationDisposition.IN_PROGRESS, current)
            elif current.state in {
                ExternalActionState.PRE_EFFECT_FAILED,
                ExternalActionState.CONFIRMED_NO_EFFECT,
            }:
                payload = {"attempt_id": attempt}
            else:
                raise CaseProductHardeningError("unsupported external action state")
            try:
                self._append(
                    identity,
                    event_type=_RESERVED,
                    payload=payload,
                    expected_head=head,
                )
            except EnterpriseContractError:
                continue
            reserved, _new_head = self._load(identity)
            if reserved is None or reserved.state is not ExternalActionState.RESERVED:
                raise CaseProductHardeningError(
                    "durable external-action reservation verification failed"
                )
            if reserved.owner_attempt_id != attempt:
                raise CaseProductHardeningError(
                    "durable external-action reservation owner mismatch"
                )
            return ReservationResult(ReservationDisposition.INVOKE_ALLOWED, reserved)
        raise CaseProductHardeningError(
            "durable external-action reservation lost repeated concurrent races"
        )

    def _owned(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> tuple[CoordinatedAction, str]:
        attempt = self._validate_attempt_id(attempt_id)
        current, head = self._load(identity)
        if current is None:
            raise CaseProductHardeningError("external action has no reservation")
        if current.state is not ExternalActionState.RESERVED:
            raise CaseProductHardeningError(
                "external action is not in an invokable reservation"
            )
        if current.owner_attempt_id != attempt:
            raise CaseProductHardeningError(
                "attempt does not own the active reservation"
            )
        return current, head

    def begin_dispatch(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        dispatch_ref: str,
        started_at: datetime | None = None,
    ) -> CoordinatedAction:
        attempt = self._validate_attempt_id(attempt_id)
        operation_ref = _text(dispatch_ref, field_name="dispatch_ref")
        current, head = self._load(identity)
        if current is None:
            raise CaseProductHardeningError("external action has no reservation")
        records = self._records(identity)
        if current.state is ExternalActionState.OUTCOME_UNKNOWN and records:
            last = records[-1]
            if last.event_type == _DISPATCHED:
                payload = _mapping(last.payload, field_name="dispatch payload")
                if (
                    payload.get("attempt_id") == attempt
                    and payload.get("dispatch_ref") == operation_ref
                ):
                    return current
            raise CaseProductHardeningError(
                "external action outcome is already unknown and requires reconciliation"
            )
        self._owned(identity, attempt_id=attempt)
        moment = started_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise CaseProductHardeningError("dispatch started_at must be timezone-aware")
        try:
            self._append(
                identity,
                event_type=_DISPATCHED,
                payload={
                    "attempt_id": attempt,
                    "dispatch_ref": operation_ref,
                    "started_at": moment.isoformat(),
                },
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            winner, _winner_head = self._load(identity)
            winner_records = self._records(identity)
            if winner is None or not winner_records:
                raise CaseProductHardeningError(
                    "external-action state changed during dispatch fencing"
                ) from exc
            last = winner_records[-1]
            if last.event_type == _DISPATCHED:
                payload = _mapping(last.payload, field_name="dispatch payload")
                if (
                    winner.owner_attempt_id == attempt
                    and payload.get("dispatch_ref") == operation_ref
                ):
                    return winner
            raise CaseProductHardeningError(
                "external-action state changed during dispatch fencing"
            ) from exc
        dispatched, _new_head = self._load(identity)
        if dispatched is None or dispatched.state is not ExternalActionState.OUTCOME_UNKNOWN:
            raise CaseProductHardeningError("durable dispatch verification failed")
        return dispatched

    def mark_pre_effect_failed(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> CoordinatedAction:
        attempt = self._validate_attempt_id(attempt_id)
        current, head = self._load(identity)
        if (
            current is not None
            and current.state is ExternalActionState.PRE_EFFECT_FAILED
            and current.owner_attempt_id == attempt
        ):
            return current
        self._owned(identity, attempt_id=attempt)
        try:
            self._append(
                identity,
                event_type=_PRE_EFFECT_FAILED,
                payload={"attempt_id": attempt},
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            raise CaseProductHardeningError(
                "external-action state changed during failure recording"
            ) from exc
        updated, _new_head = self._load(identity)
        if updated is None:
            raise CaseProductHardeningError("external-action failure record disappeared")
        return updated

    def mark_outcome_unknown(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
    ) -> CoordinatedAction:
        attempt = self._validate_attempt_id(attempt_id)
        current, head = self._load(identity)
        if (
            current is not None
            and current.state is ExternalActionState.OUTCOME_UNKNOWN
            and current.owner_attempt_id == attempt
        ):
            return current
        self._owned(identity, attempt_id=attempt)
        try:
            self._append(
                identity,
                event_type=_OUTCOME_UNKNOWN,
                payload={"attempt_id": attempt},
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            raise CaseProductHardeningError(
                "external-action state changed while marking outcome unknown"
            ) from exc
        updated, _new_head = self._load(identity)
        if updated is None:
            raise CaseProductHardeningError("external-action unknown record disappeared")
        return updated

    def confirm_no_effect(
        self,
        identity: ExternalActionIdentity,
        *,
        reconciliation_ref: str,
    ) -> CoordinatedAction:
        reconciliation = _text(
            reconciliation_ref,
            field_name="reconciliation_ref",
        )
        current, head = self._load(identity)
        if current is None:
            raise CaseProductHardeningError("external action has no reservation")
        if current.state is ExternalActionState.CONFIRMED_NO_EFFECT:
            return current
        if current.state is not ExternalActionState.OUTCOME_UNKNOWN:
            raise CaseProductHardeningError(
                "confirmed no-effect reconciliation requires OUTCOME_UNKNOWN"
            )
        try:
            self._append(
                identity,
                event_type=_CONFIRMED_NO_EFFECT,
                payload={"reconciliation_ref": reconciliation},
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            winner, _winner_head = self._load(identity)
            if winner is not None and winner.state is ExternalActionState.CONFIRMED_NO_EFFECT:
                return winner
            raise CaseProductHardeningError(
                "external-action state changed during no-effect reconciliation"
            ) from exc
        updated, _new_head = self._load(identity)
        if updated is None:
            raise CaseProductHardeningError("external-action reconciliation disappeared")
        return updated

    def confirm_success(
        self,
        identity: ExternalActionIdentity,
        *,
        attempt_id: str,
        receipt: ExternalActionReceipt,
    ) -> CoordinatedAction:
        verify_receipt_for_transition(receipt, identity)
        attempt = self._validate_attempt_id(attempt_id)
        if receipt.attempt_id != attempt:
            raise CaseProductHardeningError("receipt attempt does not match active attempt")
        current, head = self._load(identity)
        if current is not None and current.state in {
            ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
            ExternalActionState.RECEIPT_RECOVERED,
        }:
            if current.receipt == receipt:
                return current
            raise CaseProductHardeningError(
                "confirmed external action already has a different receipt"
            )
        if current is None:
            raise CaseProductHardeningError("external action has no reservation")
        if current.state is not ExternalActionState.OUTCOME_UNKNOWN:
            raise CaseProductHardeningError(
                "confirmed success requires dispatch before provider success"
            )
        if current.owner_attempt_id != attempt:
            raise CaseProductHardeningError("attempt does not own active dispatch")
        try:
            self._append(
                identity,
                event_type=_CONFIRMED_SUCCESS,
                payload={"attempt_id": attempt, "receipt": receipt.canonical_dict()},
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            winner, _winner_head = self._load(identity)
            if (
                winner is not None
                and winner.state
                in {
                    ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
                    ExternalActionState.RECEIPT_RECOVERED,
                }
                and winner.receipt == receipt
            ):
                return winner
            raise CaseProductHardeningError(
                "external-action state changed during success confirmation"
            ) from exc
        updated, _new_head = self._load(identity)
        if updated is None:
            raise CaseProductHardeningError("external-action success record disappeared")
        return updated

    def recover_receipt(
        self,
        identity: ExternalActionIdentity,
        *,
        receipt: ExternalActionReceipt,
        reconciliation_ref: str,
    ) -> CoordinatedAction:
        verify_receipt_for_transition(receipt, identity)
        reconciliation = _text(
            reconciliation_ref,
            field_name="reconciliation_ref",
        )
        current, head = self._load(identity)
        if current is None:
            raise CaseProductHardeningError("external action has no reservation")
        if current.state in {
            ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
            ExternalActionState.RECEIPT_RECOVERED,
        }:
            if current.receipt == receipt:
                return current
            raise CaseProductHardeningError(
                "external action already has a different confirmed receipt"
            )
        if current.state is not ExternalActionState.OUTCOME_UNKNOWN:
            raise CaseProductHardeningError(
                "receipt recovery requires OUTCOME_UNKNOWN"
            )
        if receipt.attempt_id != current.owner_attempt_id:
            raise CaseProductHardeningError("recovered receipt attempt mismatch")
        try:
            self._append(
                identity,
                event_type=_RECEIPT_RECOVERED,
                payload={
                    "reconciliation_ref": reconciliation,
                    "receipt": receipt.canonical_dict(),
                },
                expected_head=head,
            )
        except EnterpriseContractError as exc:
            winner, _winner_head = self._load(identity)
            if (
                winner is not None
                and winner.state
                in {
                    ExternalActionState.CONFIRMED_EXTERNAL_SUCCESS,
                    ExternalActionState.RECEIPT_RECOVERED,
                }
                and winner.receipt == receipt
            ):
                return winner
            raise CaseProductHardeningError(
                "external-action state changed during receipt recovery"
            ) from exc
        updated, _new_head = self._load(identity)
        if updated is None:
            raise CaseProductHardeningError("external-action recovered receipt disappeared")
        return updated

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
        receipt = provider_call()
        return self.confirm_success(
            identity,
            attempt_id=attempt_id,
            receipt=receipt,
        ).receipt or receipt


__all__ = [
    "DURABLE_EXTERNAL_ACTION_SCHEMA_V1",
    "DurableExternalActionCoordinator",
]
