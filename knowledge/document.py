from pathlib import Path
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Document:
    """Reprezentuje pojedynczy dokument KOS."""

    path: Path
    name: str
    extension: str
    size: int
    modified: datetime

    @classmethod
    def from_file(cls, path: Path):
        stat = path.stat()

        return cls(
            path=path,
            name=path.name,
            extension=path.suffix,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )