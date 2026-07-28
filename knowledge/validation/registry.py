"""
Knowledge Operating System (KOS)

Validation registry.
"""

from knowledge.validation.checks.cycles import CycleCheck
from knowledge.validation.checks.duplicate_edges import DuplicateEdgesCheck
from knowledge.validation.checks.missing_nodes import MissingNodesCheck
from knowledge.validation.checks.orphan_nodes import OrphanNodesCheck

DEFAULT_VALIDATION_CHECKS = (
    MissingNodesCheck(),
    CycleCheck(),
    OrphanNodesCheck(),
    DuplicateEdgesCheck(),
)
