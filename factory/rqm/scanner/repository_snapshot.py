from dataclasses import dataclass
from datetime import datetime
from typing import List

from factory.rqm.scanner.file_info import FileInfo
   
@dataclass(frozen=True)
class RepositorySnapshot:
    """Kompletny obraz repozytorium po skanowaniu."""

    files: List[FileInfo]
    statistics: Dict
    scan_time: float
    ignored_count: int
    repository_hash: str
    timestamp: datetime       n 
    