"""Real loopback WORK + PostgreSQL boundary probe; never claims full H5."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Thread
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--private-connection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.private_connection.read_text(encoding="utf-8-sig"))
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    for name, key in (("LUKART_TEST_DSN", "runtime_dsn"), ("LUKART_TEST_ADMIN_DSN", "admin_dsn")):
        values = conninfo_to_dict(cfg[key])
        if values.get("host") != "127.0.0.1" or not values.get("dbname", "").startswith(
            "lukart_stage02_test_"
        ):
            raise ValueError("ISOLATED_TEST_DATABASE_REQUIRED")
        os.environ[name] = make_conninfo(cfg[key], port="65432", connect_timeout="5")
    ros_root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(args.work_root), str(ros_root)]
    from lukart_work.operator import GeneratorPismOperator
    from lukart_work.operator_host import create_server
    from tests.test_finalization import FinalizationTests

    from core.ros_work_adapter_v1 import (
        AdapterConfig,
        AuthorityResolution,
        RosWorkAdapterError,
        RosWorkAdapterV1,
    )

    # Only create a fresh synthetic CASE; no stage05/generator regression or legal approvals.
    fixture = FinalizationTests(
        "test_public_happy_path_persists_exact_bytes_approval_and_release_chain"
    )
    fixture.setUp()
    operator = GeneratorPismOperator(
        repository=fixture.repo,
        authority=fixture.authority,
        case_profile=fixture.final_profile,
        drafting_profiles={"QUICK": fixture.profile},
        provider=fixture.provider,
        package_profile=fixture.package_profile,
    )

    def envelope(operation="ros.work.generator.assess.v1"):
        scope = str(fixture.case_id)
        return {
            "request": {
                "schema_id": "lukart.operation-contract.v1",
                "version": "1.0",
                "operation_id": operation,
                "operation": operation,
                "input": {},
            },
            "context": {
                "repository": "lukart-ros",
                "branch": "h5/native-assess-recovery-20261103",
                "worktree": "synthetic-isolated",
                "case_id": scope,
                "runtime": "python",
            },
            "preconditions": {
                "authority_ref": "synthetic-query-only",
                "lock_ref": "synthetic-lock",
                "expected_head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ros_root, text=True
                ).strip(),
            },
            "constraints": {
                "timeout_ms": 5000,
                "allowed_side_effects": [],
                "privacy_scope": scope,
                "evidence_required": [],
            },
            "idempotency": {
                "key": "h5-assess-" + str(uuid4()),
                "replay": "exact",
                "duplicate_handling": "replay-or-block",
            },
            "effects": {"declared": [], "actual": []},
            "output": {"status": None, "summary": "", "artifacts": []},
            "evidence": {"items": []},
            "errors": {"items": []},
            "privacy": {
                "scope": scope,
                "data_classification": "SYNTHETIC",
                "cross_scope_allowed": False,
            },
        }

    def start():
        server = create_server(operator, 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        adapter = RosWorkAdapterV1(
            AdapterConfig(trusted_host_url="http://127.0.0.1:" + str(server.server_port))
        )
        adapter._authority_map = {
            "synthetic-query-only": AuthorityResolution(
                authority_ref="synthetic-query-only",
                token=fixture.token,
                admitted_operations=("ros.work.generator.assess.v1",),
                tenant_id=str(fixture.tenant),
                case_id=str(fixture.case_id),
            )
        }
        return server, thread, adapter

    def stop(server, thread):
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()

    receipt = {
        "scope": "NATIVE_HTTP_ASSESS_ONLY",
        "synthetic_only": True,
        "full_h5": "BLOCKED",
        "work_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.work_root, text=True
        ).strip(),
        "ros_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ros_root, text=True
        ).strip(),
        "database_port": 65432,
        "legal_approvals_created": False,
        "checks": [],
    }
    server = thread = None
    try:
        baseline = fixture.repo.get_heads(fixture.tenant, fixture.case_id)[0]
        server, thread, adapter = start()
        request = envelope()
        first = adapter.execute(request)
        if first.status != "success":
            raise AssertionError(
                "native assess failed: " + first.summary + " " + json.dumps(first.errors)
            )
        receipt["checks"].append("native_adapter_to_operator_http_to_postgresql")
        stop(server, thread)
        server = thread = None
        # Recreate real HTTP server over the durable same CASE repository; no mock transport.
        server, thread, adapter = start()
        replay = adapter.execute(request)
        assert replay.status == "success"
        assert fixture.repo.get_heads(fixture.tenant, fixture.case_id)[0] == baseline
        receipt["checks"].append("transport_restart_replay_preserves_case_sequence")
        blocked = envelope("ros.work.generator.execute.v1")
        blocked["request"]["input"] = {"work_operation": "CreateCase"}
        try:
            adapter.execute(blocked)
            raise AssertionError("unadmitted execute was dispatched")
        except RosWorkAdapterError as error:
            assert "not admitted" in str(error)
        receipt["checks"].append("execute_gate_denied_without_case_mutation")
        assert fixture.repo.get_heads(fixture.tenant, fixture.case_id)[0] == baseline
        receipt["boundary_result"] = "PASS"
        receipt["remaining"] = (
            "Independent PB02/PB03/type admission before positive execute/package "
            "conformance; full pipeline crash recovery not tested"
        )
    except Exception as error:
        receipt["boundary_result"] = "FAIL"
        receipt["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if server is not None:
            stop(server, thread)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt))
    return 0 if receipt["boundary_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
