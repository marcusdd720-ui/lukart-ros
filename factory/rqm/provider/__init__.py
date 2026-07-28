from factory.rqm.provider.audit_provider import AuditProvider
from factory.rqm.provider.provider_registry import registry
from factory.rqm.provider.pytest_provider import PytestProvider

# Register canonical providers for RQM 4.0 P0
registry.register(PytestProvider)
registry.register(AuditProvider)
