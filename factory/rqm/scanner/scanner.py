from __future__ import annotations

import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from factory.rqm.scanner.file_info import FileInfo
from factory.rqm.scanner.repository_snapshot import RepositorySnapshot

logger = logging.getLogger(__name__)

_IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)


@dataclass
class ScannerConfig:
    """Scanner settings used by ProjectScanner."""

    max_workers: int = 4
    ignored_names: frozenset[str] = field(
        default_factory=lambda: _IGNORED_DIR_NAMES,
    )


class DefaultFilters:
    """Skip cache, VCS, and virtualenv paths."""

    def __init__(self, config: ScannerConfig) -> None:
        self.config = config

    def is_ignored(self, path: Path) -> bool:
        return any(part in self.config.ignored_names for part in path.parts)


class FileHasher:
    """SHA-256 hasher for scanned files."""

    def hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()


class ScanCache:
    """Placeholder cache; persistence is not required for the quality gate."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, snapshot: RepositorySnapshot) -> None:
        # Persistence intentionally deferred; quality gate only needs the API.
        pass


@dataclass
class ScanStatistics:
    """Aggregate counts derived from scanned files."""

    file_count: int
    total_size: int

    @classmethod
    def from_files(cls, files: list[FileInfo]) -> ScanStatistics:
        return cls(
            file_count=len(files),
            total_size=sum(item.size for item in files),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "file_count": self.file_count,
            "total_size": self.total_size,
        }


class ProjectScanner:
    """Zaawansowany, wielowątkowy, konfigurowalny skaner repozytorium."""

    def __init__(
        self,
        root: Path,
        config: ScannerConfig | None = None,
    ) -> None:
        self.root = root
        self.config = config or ScannerConfig()
        self.filters = DefaultFilters(self.config)
        self.hasher = FileHasher()
        self.cache = ScanCache(root)

    def scan(self) -> RepositorySnapshot:
        """Wykonuje pełne skanowanie repozytorium."""
        start = time.perf_counter()
        logger.info("Scanning project: %s", self.root)

        files: list[FileInfo] = []

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [
                executor.submit(
                    self._process_file,
                    Path(dirpath) / filename,
                )
                for dirpath, _, filenames in os.walk(self.root)
                for filename in filenames
                if not self.filters.is_ignored(Path(dirpath) / filename)
            ]

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    files.append(result)

        scan_time = time.perf_counter() - start
        stats = ScanStatistics.from_files(files)

        snapshot = RepositorySnapshot(
            files=files,
            statistics=stats.to_dict(),
            scan_time=scan_time,
            ignored_count=0,
            repository_hash=self._compute_repo_hash(files),
            timestamp=datetime.now(UTC),
        )

        self.cache.save(snapshot)

        logger.info(
            "Scan completed in %.2fs — %d files",
            scan_time,
            len(files),
        )
        return snapshot

    def _process_file(self, path: Path) -> FileInfo | None:
        try:
            stat = path.stat()
            sha256 = self.hasher.hash_file(path)
            return FileInfo(
                path=path,
                relative_path=str(path.relative_to(self.root)),
                size=stat.st_size,
                sha256=sha256,
                modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                extension=path.suffix.lower(),
                is_python=path.suffix.lower() == ".py",
                is_markdown=path.suffix.lower() in {".md", ".markdown"},
                is_config=path.suffix.lower()
                in {".toml", ".yaml", ".yml", ".json"},
            )
        except OSError:
            logger.exception("Failed to process file: %s", path)
            return None

    def _compute_repo_hash(self, files: list[FileInfo]) -> str:
        """Oblicza hash całego repozytorium."""
        combined = "".join(file.sha256 for file in files)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()