from __future__ import annotations

from factory.rqm.audit.rule import AuditRule


class AuditRegistry:
    """
    Registry of audit rules.

    Stores rule classes and creates rule instances on demand.
    """

    def __init__(self) -> None:
        self._rules: list[type[AuditRule]] = []

    def register(self, rule_cls: type[AuditRule]) -> None:
        """
        Register a new audit rule.
        """

        if not issubclass(rule_cls, AuditRule):
            raise TypeError(f"{rule_cls!r} is not a subclass of AuditRule")

        if rule_cls not in self._rules:
            self._rules.append(rule_cls)

    def unregister(self, rule_cls: type[AuditRule]) -> None:
        """
        Remove a rule from the registry.
        """

        if rule_cls in self._rules:
            self._rules.remove(rule_cls)

    def create_all(self) -> list[AuditRule]:
        """
        Create instances of all registered rules.
        """

        return [rule_cls() for rule_cls in self._rules]

    def clear(self) -> None:
        """
        Remove all registered rules.
        """

        self._rules.clear()

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self.create_all())
