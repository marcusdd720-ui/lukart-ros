from __future__ import annotations
import ast
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from validation.code_audit.models import Finding


class BaseRule(ABC):
    rule_id: str = "BASE"
    description: str = ""

    @abstractmethod
    def check(self, tree: ast.AST, file_path: Path) -> List[Finding]:
        ...
