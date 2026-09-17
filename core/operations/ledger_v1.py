"""Thread-safe exact-replay idempotency ledger for Operation Contract v1."""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Mapping
from typing import Any

from .types_v1 import OperationContractError


class IdempotencyLedger:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._records: dict[str, dict[str, Any]] = {}

    def reserve(
        self,
        key: str,
        digest: str,
        deadline: float,
    ) -> tuple[str, dict[str, Any] | None]:
        with self._condition:
            record = self._records.get(key)
            if record is None:
                self._records[key] = {"digest": digest, "state": "running", "result": None}
                return "execute", None
            if record["digest"] != digest:
                return "conflict", None
            while record["state"] == "running":
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return "timeout", None
                self._condition.wait(remaining)
            stored = record["result"]
            if not isinstance(stored, Mapping):
                raise OperationContractError("idempotency record is corrupt")
            return "replay", copy.deepcopy(dict(stored))

    def complete(self, key: str, execution: Mapping[str, object]) -> None:
        with self._condition:
            record = self._records.get(key)
            if record is None or record["state"] != "running":
                raise OperationContractError("idempotency reservation is missing")
            record["state"] = "done"
            record["result"] = copy.deepcopy(dict(execution))
            self._condition.notify_all()
