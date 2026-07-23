from pathlib import Path

from validation.consistency_checker import ConsistencyChecker


class ValidationEngine:
    """
    Główny silnik walidacji projektu.
    """

    def __init__(self):
        self.checkers = [
            ConsistencyChecker(),
        ]

    def validate(self, project_path: str) -> list[dict]:
        """
        Uruchamia wszystkie walidatory.
        """

        project = Path(project_path)

        results = []

        for checker in self.checkers:
            results.append(checker.check(project))

        return results

    def passed(self, project_path: str) -> bool:
        """
        Zwraca True jeśli wszystkie walidacje zakończyły się sukcesem.
        """

        results = self.validate(project_path)

        return all(result["passed"] for result in results)