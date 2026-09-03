"""Import source documents into a private local MVROS case."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.local_case_store import case_dir, ensure_data_root, validate_case_key


class ImportManager:
    """Copy source documents only into the private local case store."""

    def __init__(self, cases_root: str | None = None):
        self.data_root = ensure_data_root(Path(cases_root).expanduser() if cases_root else None)

    @property
    def cases_root(self) -> Path:
        return self.data_root / "cases"

    def get_original_folder(self, case_id: str) -> Path:
        safe_key = validate_case_key(case_id)
        case_path = case_dir(safe_key, self.data_root)
        if not case_path.exists():
            raise FileNotFoundError(f"CASE '{safe_key}' does not exist in the private local store.")
        original = case_path / "original"
        if not original.exists():
            raise FileNotFoundError("'original' folder does not exist.")
        return original

    def _unique_target(self, target: Path) -> Path:
        if not target.exists():
            return target
        counter = 1
        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def import_directory(self, case_id: str, source_directory: str) -> tuple[int, int]:
        """Import regular files into the local CASE/original directory.

        Symlinks are rejected so an import cannot follow an external filesystem
        object into an unintended location.
        """
        destination = self.get_original_folder(case_id).resolve()
        source = Path(source_directory).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source directory '{source}' does not exist.")
        if not source.is_dir():
            raise NotADirectoryError(f"'{source}' is not a directory.")

        files_count = 0
        folders_count = 0
        for item in source.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Symlink input is not allowed: {item}")
            relative = item.relative_to(source)
            target = (destination / relative).resolve()
            if destination != target and destination not in target.parents:
                raise ValueError(f"Import target escapes case directory: {relative}")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                folders_count += 1
            elif item.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, self._unique_target(target))
                files_count += 1
        return files_count, folders_count
