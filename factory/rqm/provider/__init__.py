from factory.rqm.providers.provider_registry import registry
from factory.rqm.providers.pytest_provider import PytestProvider
from factory.rqm.providers.audit_provider import AuditProvider

# Register canonical providers for RQM 4.0 P0
registry.register(PytestProvider)
registry.register(AuditProvider)