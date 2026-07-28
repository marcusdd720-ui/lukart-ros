from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class FileInfo:
    """Niezmienny model pliku — bogaty w metadane."""

    path: Path
    relative_path: str
    size: int
    sha256: str
    modified: datetime
    extension: str
    is_python: bool
    is_markdown: bool
    is_config: bool
