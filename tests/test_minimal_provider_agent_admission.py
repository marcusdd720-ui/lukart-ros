"""Minimal provider/agent admission contract; no credentials or network calls.

These are focused fail-closed preflight checks, not a substitute for runtime
isolation evidence, independent review or a real provider invocation.
"""

import shlex
import socket
import socketserver
import threading
import time
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml"
ADAPTERS = ROOT / "docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_ADAPTERS_V1.yaml"
WORKFLOW = ROOT / ".github/workflows/night-shift-opencode-groq-p0.yml"


def _unique_bindings(adapters: dict) -> dict:
    entries = adapters["bindings"]
    ids = [item["executor_id"] for item in entries]
    assert len(ids) == len(set(ids)), "duplicate adapter executor_id"
    return {item["executor_id"]: item for item in entries}


def _assert_docker_run_sandbox(isolation: dict) -> None:
    commands = []
    for step in isolation["steps"]:
        lines = step.get("run", "").splitlines()
        for index, line in enumerate(lines):
            if not line.lstrip().startswith("docker run "):
                continue
            parts = [line.strip()]
            while parts[-1].endswith("\\"):
                index += 1
                assert index < len(lines), "unterminated docker run command"
                parts.append(lines[index].strip())
            commands.append(" ".join(part.removesuffix("\\").strip() for part in parts))
    assert len(commands) == 4, "unexpected number of Docker invocations"

    # Parse exact shell arguments, not substrings (including inside --env values).
    image = (
        "python:3.12.14-slim@sha256:"
        "2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79"
    )
    valued = {
        "--platform", "--network", "--user", "--cap-drop", "--security-opt",
        "--pids-limit", "--memory", "--cpus", "--mount", "--tmpfs",
        "--name", "--env",
    }
    switches = {"--rm", "-d", "--read-only"}
    expected = {
        "--platform": "linux/amd64",
        "--user": "65534:65534",
        "--cap-drop": "ALL",
        "--security-opt": "no-new-privileges",
        "--pids-limit": "32",
        "--memory": "128m",
        "--cpus": "1",
        "--read-only": "true",
    }
    networks = []
    for command in commands:
        assert command.count(" " + image) == 1, "missing or ambiguous pinned Docker image"
        prefix = command.split(" " + image, 1)[0]
        args = shlex.split(prefix)
        assert args[:2] == ["docker", "run"], "unexpected Docker invocation"
        options: dict[str, str] = {}
        index = 2
        while index < len(args):
            flag = args[index]
            assert flag not in options, f"duplicate Docker option {flag}"
            if flag in switches:
                options[flag] = "true"
                index += 1
            else:
                assert flag in valued, f"unexpected Docker option {flag}"
                assert index + 1 < len(args), f"Docker option without value: {flag}"
                options[flag] = args[index + 1]
                index += 2
        for flag, value in expected.items():
            assert options.get(flag) == value, f"missing {flag} {value} in Docker invocation"
        assert "--network" in options, "Docker invocation without network declaration"
        networks.append(options["--network"])
    assert sorted(networks) == sorted(["none", "bridge", "bridge", "$net"])


def test_all_registered_agents_have_bounded_unique_identity_and_adapter() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    adapters = yaml.safe_load(ADAPTERS.read_text(encoding="utf-8"))
    executors = registry["executors"]
    bindings = _unique_bindings(adapters)
    ids = [item["executor_id"] for item in executors]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(bindings)
    for executor in executors:
        assert executor["capabilities"]
        assert isinstance(executor["mutating"], bool)
        assert isinstance(executor["independent_review"], bool)
        assert executor["max_parallel"] >= 1
        assert executor["cost_rank"] >= 0
        assert bindings[executor["executor_id"]]["status"] in {
            "VALIDATED", "DOCUMENTED_ONLY",
        }


def test_pr_workflow_is_secret_free_and_not_manually_dispatchable() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    assert set(workflow["on"]) == {"pull_request"}
    assert set(workflow["on"]["pull_request"]["paths"]) == {
        ".github/workflows/night-shift-opencode-groq-p0.yml",
        "scripts/groq_connect_proxy.py",
    }
    assert workflow["concurrency"]["group"] == (
        "ros-opencode-groq-p0-${{ github.event_name }}-${{ github.ref }}"
    )
    assert workflow["concurrency"]["cancel-in-progress"] == (
        "${{ github.event_name == 'pull_request' }}"
    )
    assert set(workflow["jobs"]) == {"isolation-proof"}
    assert workflow["permissions"] == {"contents": "read"}
    isolation = workflow["jobs"]["isolation-proof"]
    assert isolation["timeout-minutes"] <= 6
    assert isolation["permissions"] == {"contents": "read"}
    assert isolation["if"] == "${{ github.event_name == 'pull_request' }}"
    # The PR-controlled file must never contain a credentialed execution path.
    assert "secrets" not in raw.lower()
    for forbidden in ("GROQ_KEY", "GROQ_API_KEY", "workflow_dispatch:"):
        assert forbidden not in raw
    _assert_docker_run_sandbox(isolation)


def test_all_external_providers_fail_closed_until_runtime_evidence() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    adapters = yaml.safe_load(ADAPTERS.read_text(encoding="utf-8"))
    bindings = _unique_bindings(adapters)
    for executor in registry["executors"]:
        binding = bindings[executor["executor_id"]]
        if binding["adapter_kind"] in {"external_provider", "external_review"}:
            # Registry availability != admission / successful provider execution.
            assert binding["status"] == "DOCUMENTED_ONLY"


def test_duplicate_adapter_bindings_fail_closed() -> None:
    entries = [
        {"executor_id": "same", "adapter_kind": "external_provider", "status": "UNVERIFIED"},
        {"executor_id": "same", "adapter_kind": "local", "status": "VALIDATED"},
    ]
    with pytest.raises(AssertionError, match="duplicate adapter executor_id"):
        _unique_bindings({"bindings": entries})


def test_docker_sandbox_rejects_one_weakened_invocation() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    isolation = workflow["jobs"]["isolation-proof"]
    _assert_docker_run_sandbox(isolation)
    weakened = deepcopy(isolation)
    for step in weakened["steps"]:
        run = step.get("run", "")
        if "docker run " in run:
            step["run"] = run.replace("--cap-drop ALL", "--cap-drop NONE", 1)
            break
    else:
        raise AssertionError("No Docker invocation to mutate")
    with pytest.raises(AssertionError, match="missing --cap-drop ALL"):
        _assert_docker_run_sandbox(weakened)


def test_docker_sandbox_rejects_cap_drop_spoofed_by_env() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    weakened = deepcopy(workflow["jobs"]["isolation-proof"])
    for step in weakened["steps"]:
        run = step.get("run", "")
        if "docker run " in run:
            step["run"] = run.replace(
                "--cap-drop ALL", "--env 'SANDBOX_CHECK=--cap-drop ALL'", 1
            )
            break
    else:
        raise AssertionError("No Docker invocation to mutate")
    with pytest.raises(AssertionError, match="missing --cap-drop ALL"):
        _assert_docker_run_sandbox(weakened)


def test_proxy_forwards_full_payload_with_local_backpressure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Loopback only: no provider, external network or API credentials involved.
    from scripts import groq_connect_proxy as proxy

    payload = bytes(range(256)) * 2048
    original_sendall = socket.socket.sendall

    def guarded_sendall(sock: socket.socket, data: bytes) -> None:
        # Emulate EWOULDBLOCK on non-blocking writes deterministically.
        if not sock.getblocking():
            raise BlockingIOError("non-blocking send could not complete")
        return original_sendall(sock, data)

    monkeypatch.setattr(socket.socket, "sendall", guarded_sendall)

    class Echo(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            data = bytearray()
            while len(data) < len(payload):
                chunk = self.request.recv(65536)
                if not chunk:
                    return
                data.extend(chunk)
            self.request.sendall(data)

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Echo) as upstream:
        upstream.daemon_threads = True
        monkeypatch.setattr(proxy, "ALLOWED_HOST", "127.0.0.1")
        monkeypatch.setattr(proxy, "ALLOWED_PORT", upstream.server_address[1])
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            with proxy._Proxy(("127.0.0.1", 0), proxy._ConnectHandler) as server:
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                try:
                    address = ("127.0.0.1", int(server.server_address[1]))
                    with socket.create_connection(address, 5) as client:
                        client.settimeout(10)
                        client.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\n\r\n")
                        response = bytearray()
                        while b"\r\n\r\n" not in response:
                            response.extend(client.recv(1))
                        assert bytes(response).startswith(b"HTTP/1.1 200")
                        client.sendall(payload)
                        time.sleep(0.05)  # exercise relay while receiver is paused
                        echoed = bytearray()
                        while len(echoed) < len(payload):
                            chunk = client.recv(65536)
                            assert chunk, "premature proxy tunnel close"
                            echoed.extend(chunk)
                        assert bytes(echoed) == payload
                finally:
                    server.shutdown()
                    server_thread.join(timeout=5)
        finally:
            upstream.shutdown()
            upstream_thread.join(timeout=5)
