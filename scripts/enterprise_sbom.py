from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.enterprise.supply_chain import build_cyclonedx_sbom


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LUKART resolved-runtime CycloneDX SBOM")
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--output", default="build/enterprise/bom.cdx.json")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    bom = build_cyclonedx_sbom(args.pyproject)
    output.write_text(
        json.dumps(bom, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ENTERPRISE_SBOM={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
