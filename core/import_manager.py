from pathlib import Path
import shutil


class ImportManager:
    """
    Responsible for importing documents into a CASE.
    """

    def __init__(self, cases_root: str = "cases"):
        self.cases_root = Path(cases_root)

    def get_original_folder(self, case_id: str) -> Path:
        case_path = self.cases_root / case_id

        if not case_path.exists():
            raise FileNotFoundError(f"CASE '{case_id}' does not exist.")

        original = case_path / "original"

        if not original.exists():
            raise FileNotFoundError("'original' folder does not exist.")

        return original

    def import_directory(self, case_id: str, source_directory: str) -> tuple[int, int]:
        """
        Import all files and folders into CASE/original.
        Returns:
            (files_count, folders_count)
        """

        destination = self.get_original_folder(case_id)

        source = Path(source_directory)

        if not source.exists():
            raise FileNotFoundError(f"Source directory '{source}' does not exist.")

        if not source.is_dir():
            raise NotADirectoryError(f"'{source}' is not a directory.")

        files_count = 0
        folders_count = 0

        for item in source.rglob("*"):

            relative = item.relative_to(source)
            target = destination / relative

            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                folders_count += 1

            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                files_count += 1

        return files_count, folders_count