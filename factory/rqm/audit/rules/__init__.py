"""
RQM Audit Rules Library
"""

from factory.rqm.audit.rules.duplicate_file_rule import DuplicateFileRule
from factory.rqm.audit.rules.empty_directory_rule import EmptyDirectoryRule
from factory.rqm.audit.rules.gitignore_rule import GitignoreRule
from factory.rqm.audit.rules.init_rule import InitRule
from factory.rqm.audit.rules.large_file_rule import LargeFileRule
from factory.rqm.audit.rules.license_rule import LicenseRule
from factory.rqm.audit.rules.pyproject_rule import PyprojectRule
from factory.rqm.audit.rules.readme_rule import ReadmeRule
from factory.rqm.audit.rules.todo_rule import TodoRule
from factory.rqm.audit.rules.workflow_rule import WorkflowRule

ALL_RULES = [
    ReadmeRule,
    LicenseRule,
    GitignoreRule,
    WorkflowRule,
    PyprojectRule,
    InitRule,
    EmptyDirectoryRule,
    TodoRule,
    LargeFileRule,
    DuplicateFileRule,
]

__all__ = [
    "ALL_RULES",
    "ReadmeRule",
    "LicenseRule",
    "GitignoreRule",
    "WorkflowRule",
    "PyprojectRule",
    "InitRule",
    "EmptyDirectoryRule",
    "TodoRule",
    "LargeFileRule",
    "DuplicateFileRule",
]