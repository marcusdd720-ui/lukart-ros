from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "validation" / "run_h5_native_assess.py"
_SPEC = importlib.util.spec_from_file_location("run_h5_native_assess_guard", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_validate = _MODULE._validate_isolated_dsn_values


def _base_values() -> dict[str, str]:
    return {"host": "127.0.0.1", "dbname": "lukart_stage02_test_synthetic"}


def test_accepts_exact_loopback_test_dsn() -> None:
    _validate(_base_values())
    _validate(_base_values() | {"hostaddr": "127.0.0.1"})


@pytest.mark.parametrize(
    "changes",
    (
        {"host": "localhost"},
        {"host": "127.0.0.1,203.0.113.10"},
        {"hostaddr": "203.0.113.10"},
        {"hostaddr": "127.0.0.1,203.0.113.10"},
        {"hostaddr": ""},
        {"service": "remote-service"},
        {"servicefile": "remote-service.conf"},
        {"dbname": "production"},
    ),
)
def test_rejects_non_isolated_or_overridden_dsn(changes: dict[str, str]) -> None:
    values = _base_values() | changes
    with pytest.raises(ValueError, match="ISOLATED_TEST_DATABASE_REQUIRED"):
        _validate(values)
