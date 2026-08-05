"""Repository audit provider for RQM – runs full audit rule library."""

from __future__ import annotations

import time

from factory.rqm.audit.engine import AuditEngine
from factory.rqm.audit.registry import AuditRegistry
from factory.rqm.audit.rules import ALL_RULES
from factory.rqm.model import Finding, Result, Severity
from factory.rqm.provider.base_provider import BaseProvider


class AuditProvider(BaseProvider):
    """Runs registered audit rules against the repository root."""

    provider_name = "audit"

    @property
    def name(self) -> str:
        return self.provider_name

    def run(self) -> Result:
        start = time.perf_counter()

        try:
            registry = AuditRegistry()
            for rule_cls in ALL_RULES:
                registry.register(rule_cls)

            engine = AuditEngine(root=self.root, registry=registry)
            raw_findings = engine.run()
            findings = [self._normalize_finding(item) for item in raw_findings]

            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                findings=findings,
                metadata={
                    "rules": len(registry),
                    "engine": "AuditEngine",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                metadata={"exception": exc.__class__.__name__},
                findings=[
                    Finding(
                        rule_id="AUDIT_PROVIDER_ERROR",
                        severity=Severity.ERROR,
                        message=str(exc),
                        file=None,
                        line=None,
                    )
                ],
            )

    @staticmethod
    def _normalize_finding(item: Finding | object) -> Finding:
        """Ensure severity is Severity enum (rules may pass plain strings)."""
        if isinstance(item, Finding) and isinstance(item.severity, Severity):
            return item

        rule_id = str(getattr(item, "rule_id", "UNKNOWN"))
        message = str(getattr(item, "message", ""))
        file = getattr(item, "file", None)
        line = getattr(item, "line", None)
        category = str(getattr(item, "category", "general") or "general")

        raw = getattr(item, "severity", Severity.WARNING)
        if isinstance(raw, Severity):
            severity = raw
        else:
            text = str(raw).upper()
            severity = (
                Severity[text] if text in Severity.__members__ else Severity.WARNING
            )

        return Finding(
            rule_id=rule_id,
            severity=severity,
            message=message,
            file=file,
            line=line,
            category=category,
            provider="audit",
        )