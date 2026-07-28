from pathlib import Path


class ConsistencyChecker:
    """
    Sprawdza podstawową spójność projektu.
    """

    REQUIRED_DIRECTORIES = [
        "core",
        "knowledge",
        "validation",
        "tests",
    ]

    def check(self, project: Path) -> dict:
        missing = []

        for directory in self.REQUIRED_DIRECTORIES:
            if not (project / directory).exists():
                missing.append(directory)

        return {
            "name": "Consistency Checker",
            "passed": len(missing) == 0,
            "missing": missing,
        }
