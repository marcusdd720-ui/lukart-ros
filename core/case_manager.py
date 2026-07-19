from pathlib import Path
from datetime import date
import yaml


class CaseManager:
    """
    Responsible for creating and managing CASE directories.
    """

    def __init__(self, cases_root: str = "cases"):
        self.cases_root = Path(cases_root)
        self.cases_root.mkdir(exist_ok=True)

    def create_case(self) -> Path:
        """
        Creates the next available CASE directory.
        Example:
            CASE-0001
            CASE-0002
        """

        case_id = self._next_case_id()
        case_path = self.cases_root / case_id

        case_path.mkdir()

        folders = [
            "original",
            "extracted",
            "markdown",
            "evidence",
            "timeline",
            "reports",
            "exports",
        ]

        for folder in folders:
            (case_path / folder).mkdir()

        metadata = {
            "id": case_id,
            "title": "",
            "institution": "",
            "case_number": "",
            "status": "active",
            "created": str(date.today()),
            "version": "1.0",
        }

        with open(case_path / "case.yaml", "w", encoding="utf-8") as file:
            yaml.safe_dump(
                metadata,
                file,
                allow_unicode=True,
                sort_keys=False,
            )

        return case_path

    def _next_case_id(self) -> str:
        existing = []

        for directory in self.cases_root.iterdir():
            if directory.is_dir() and directory.name.startswith("CASE-"):
                try:
                    existing.append(int(directory.name.split("-")[1]))
                except ValueError:
                    pass

        next_number = max(existing, default=0) + 1

        return f"CASE-{next_number:04d}"