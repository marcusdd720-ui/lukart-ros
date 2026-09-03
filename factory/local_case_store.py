"""Compatibility exports for factory-local integrations.

Runtime code must import storage policy from ``core.local_case_store``.
The factory keeps this module only for backwards compatibility with tooling.
"""

from core.local_case_store import (
    PrivacyViolation,
    case_dir,
    default_data_root,
    ensure_data_root,
    find_repo_root,
    output_case_dir,
    save_source_snapshot,
    source_snapshot_dir,
    validate_case_key,
    validate_data_root,
)

__all__ = [
    "PrivacyViolation",
    "case_dir",
    "default_data_root",
    "ensure_data_root",
    "find_repo_root",
    "output_case_dir",
    "save_source_snapshot",
    "source_snapshot_dir",
    "validate_case_key",
    "validate_data_root",
]
