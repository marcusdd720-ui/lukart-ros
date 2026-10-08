"""Real-process fixtures used to prove mutating builder/reviewer handoff."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    mode = sys.argv[1]
    product = Path("product.txt")
    if mode == "build":
        product.write_text("bounded-zero-cost-builder-output\n", encoding="utf-8")
        print("LUKART_PROGRESS:workspace-mutated", flush=True)
        print("BUILDER_PASS", flush=True)
        return 0
    if mode == "review":
        if product.read_text(encoding="utf-8") != "bounded-zero-cost-builder-output\n":
            return 3
        print("LUKART_PROGRESS:independent-review-complete", flush=True)
        print("REVIEWER_PASS", flush=True)
        return 0
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
