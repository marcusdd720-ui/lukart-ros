"""Fail closed on API tool-transport fields before any Groq egress."""

from __future__ import annotations

import json
import socket

import pytest

from core.night_shift.groq_local_broker import GroqBrokerPolicy, GroqLocalBroker


@pytest.mark.parametrize("field,value", [
    ("tools", [{"type": "function", "function": {"name": "exec"}}]),
    ("tool_choice", "auto"),
    ("tools", None),
    ("tool_choice", None),
    ("functions", [{"name": "legacy"}]),
    ("function_call", "auto"),
])
def test_tool_transport_is_denied_before_upstream(
    tmp_path, monkeypatch, field, value,
):
    marker = "ROS_SCOPE_TOOL_DENY_2026_10"
    socket_dir = tmp_path / "private"
    socket_dir.mkdir(mode=0o700)
    policy = GroqBrokerPolicy(task_id="synthetic", task_marker=marker)
    attempted = []

    def refuse_outbound(*args, **kwargs):
        attempted.append((args, kwargs))
        raise AssertionError("unsupported tool transport reached upstream")

    monkeypatch.setattr("urllib.request.build_opener", refuse_outbound)
    with GroqLocalBroker(
        socket_path=socket_dir / "broker.sock", policy=policy,
        api_key="gsk_" + "S" * 32,
    ) as broker:
        body = json.dumps({
            "model": "openai/gpt-oss-120b", "stream": True,
            "messages": [{"role": "user", "content": marker}], field: value,
        }).encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(broker.socket_path))
            headers = (
                "POST /openai/v1/chat/completions HTTP/1.0\r\n"
                f"Host: local\r\nContent-Length: {len(body)}\r\n\r\n"
            )
            client.sendall(headers.encode() + body)
            output = bytearray()
            while data := client.recv(4096):
                output.extend(data)
        header, _, payload = bytes(output).partition(b"\r\n\r\n")
        assert header.split(b" ")[1] == b"403"
        assert b"UNSUPPORTED_TOOL_TRANSPORT" in payload
        assert broker.evidence.upstream_statuses == []
    assert not attempted
