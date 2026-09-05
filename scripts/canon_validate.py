"""CLI entry point for KMeta Canon contract validation."""

from __future__ import annotations

import sys
from pathlib import Path

from validation.canon_contracts import validate_canon_directory


def main() -> int:
    violations = validate_canon_directory(Path("canon"))
    if not violations:
        print("CANON_CONTRACTS: PASS")
        return 0

    print("CANON_CONTRACTS: FAIL")
    for violation in violations:
        print(f"{violation.path}: {violation.code}: {violation.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
