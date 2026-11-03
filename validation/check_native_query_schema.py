"""Cross-repository schema regression: adapter query must parse as native WORK."""

import argparse
import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work-root", type=Path, required=True)
    args = p.parse_args()
    sys.path[:0] = [str(args.work_root), str(Path(__file__).resolve().parents[1])]
    CoreQuery = importlib.import_module("lukart_work.core.requests").CoreQuery

    from core.ros_work_adapter_v1 import AdapterConfig, AuthorityResolution, RosWorkAdapterV1

    adapter = RosWorkAdapterV1(AdapterConfig())
    case, tenant = str(uuid4()), str(uuid4())
    adapter._authority_map = {
        "query-only": AuthorityResolution(
            "query-only", "synthetic-token", ("ros.work.generator.assess.v1",), tenant, case
        )
    }
    value = {
        "request": {
            "operation_id": "ros.work.generator.assess.v1",
            "operation": "ros.work.generator.assess.v1",
            "input": {},
        },
        "context": {"case_id": case},
        "preconditions": {"authority_ref": "query-only"},
        "idempotency": {"key": "synthetic-query-key"},
        "constraints": {"timeout_ms": 5000},
    }
    mapped = adapter.map_request(value)
    parsed = CoreQuery.model_validate_json(json.dumps(mapped.payload))
    assert str(parsed.tenant_id) == tenant and str(parsed.case_id) == case
    assert parsed.operation == "GetCaseHead"
    assert mapped.idempotency_key == "synthetic-query-key"
    assert "meta" not in mapped.payload
    print(
        json.dumps(
            {
                "native_query_schema": "PASS",
                "scope_exact": True,
                "idempotency_binding_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
