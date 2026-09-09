"""Local non-cloud key-file provider for private evidence operations.

The provider is intentionally narrow: one explicit key id/version maps to one local
32-byte key file. Key bytes are never returned in metadata, logs, or exceptions.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.local_case_store import validate_untrusted_path
from core.private_evidence_v1 import PrivateEvidenceError


class LocalFileEvidenceKeyProvider:
    """Resolve one AES-256 key from a non-symlink local file outside GitHub."""

    def __init__(
        self,
        key_file: Path,
        *,
        key_id: str,
        key_version: int,
    ) -> None:
        self.key_id = key_id.strip()
        self.key_version = key_version
        if not self.key_id or self.key_version < 1:
            raise PrivateEvidenceError("key id and positive key version are required")
        try:
            unresolved = validate_untrusted_path(key_file, label="evidence key file")
        except RuntimeError as exc:
            raise PrivateEvidenceError("evidence key file path is invalid") from exc
        if not unresolved.is_file():
            raise PrivateEvidenceError("evidence key file must be a regular file")
        self.key_file = unresolved.resolve()

    def get_key(self, key_id: str, key_version: int) -> bytes:
        if key_id.strip() != self.key_id or key_version != self.key_version:
            raise PrivateEvidenceError("requested evidence key identity is unavailable")
        before = self.key_file.stat()
        if os.name != "nt" and before.st_mode & 0o077:
            raise PrivateEvidenceError("evidence key file permissions are too broad")
        payload = self.key_file.read_bytes()
        after = self.key_file.stat()
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise PrivateEvidenceError("evidence key file changed during read")
        if len(payload) != 32:
            raise PrivateEvidenceError("evidence key file must contain exactly 32 raw bytes")
        return payload
