from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
import logging
import time
import os

from factory.rqm.scanner.file_info import FileInfo
from factory.rqm.scanner.repository_snapshot import RepositorySnapshot
from factory.rqm.scanner.filters import DefaultFilters
from factory.rqm.scanner.hasher import FileHasher
from factory.rqm.scanner.statistics import ScanStatistics
from factory.rqm.scanner.events import ScanCompletedEvent
from factory.rqm.scanner.cache import ScanCache
from factory.rqm.scanner.config import ScannerConfig

logger = logging.getLogger(__name__)

class ProjectScanner:
    """Zaawansowany, wielowątkowy, konfigurowalny scanner."""

    def __init__(self, root: Path, config: Optional[ScannerConfig] = None):
        self.root = root
        self.config = config or ScannerConfig()
        self.filters = DefaultFilters(self.config)
        self.hasher = FileHasher()
        self.cache = ScanCache(root)

    def scan(self) -> RepositorySnapshot:
        """Główne skanowanie — zwraca pełny snapshot repozytorium."""
        start = time.time()

        logger.info(f"Scanning project: {self.root}")

        files = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [
                executor.submit(self._process_file, Path(dirpath) / filename)
                for dirpath, _, filenames in os.walk(self.root)
                for filename in filenames
                if not self.filters.is_ignored(Path(dirpath) / filename)
            ]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    files.append(result)

        scan_time = time.time() - start
        stats = ScanStatistics.from_files(files)

        snapshot = RepositorySnapshot(
            files=files,
            statistics=stats.to_dict(),
            scan_time=scan_time,
            ignored_count=0,
            repository_hash=self._compute_repo_hash(files),
            timestamp=datetime.now()
        )

        self.cache.save(snapshot)
        logger.info(f"Scan completed in {scan_time:.2f}s — {len(files)} files")

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
                modified=datetime.fromtimestamp(stat.st_mtime),
                extension=path.suffix.lower(),
                is_python=path.suffix.lower() == '.py',
                is_markdown=path.suffix.lower() in {'.md', '.markdown'},
                is_config=path.suffix.lower() in {'.toml', '.yaml', '.yml', '.json'}
            )
        except Exception as e:
            logger.warning(f"Failed to process {path}: {e}")
            return None

    def _compute_repo_hash(self, files: List[FileInfo]) -> str:
        """Hash całego repozytorium."""
        combined = "".join(f.sha256 for f in files)
        return hashlib.sha256(combined.encode()).hexdigest()