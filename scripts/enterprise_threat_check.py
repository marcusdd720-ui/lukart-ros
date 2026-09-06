from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.enterprise.contracts import (
    Threat,
    ThreatModel,
    ThreatSeverity,
    TrustZone,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LUKART Enterprise threat model")
    parser.add_argument("--path", default="config/enterprise_threat_model_v1.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    threats = tuple(
        Threat(
            threat_id=str(item["threat_id"]),
            source_zone=TrustZone(str(item["source_zone"])),
            target_zone=TrustZone(str(item["target_zone"])),
            asset=str(item["asset"]),
            attack=str(item["attack"]),
            severity=ThreatSeverity(str(item["severity"])),
            mitigations=tuple(str(value) for value in item["mitigations"]),
            evidence_ids=tuple(str(value) for value in item["evidence_ids"]),
        )
        for item in payload["threats"]
    )
    model = ThreatModel(threats)
    model.require_zone_coverage(tuple(TrustZone))
    print(f"ENTERPRISE_THREATS={len(model.threats)}")
    print(f"ENTERPRISE_THREAT_MODEL_DIGEST={model.digest()}")
    print("ENTERPRISE_THREAT_MODEL=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
