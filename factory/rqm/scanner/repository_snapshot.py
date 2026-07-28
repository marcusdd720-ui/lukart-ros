from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from factory.rqm.scanner.file_info import FileInfo


@dataclass(frozen=True)
class RepositorySnapshot:
    """
    Complete immutable snapshot of the repository after scanning.
    """

    files: list[FileInfo]

    statistics: dict

    scan_time: float

    ignored_count: int

    repository_hash: str

    timestamp: datetime