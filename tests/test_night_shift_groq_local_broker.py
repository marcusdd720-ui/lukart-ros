"""Credential-free adversarial checks for the local Groq admission boundary."""

from __future__ import annotations

import io
import json
import socket
import stat
import threading
from http.server import BaseHTTPRequestHandler

import pytest

from core.night_shift.groq_local_broker import (
    GROQ_ENDPOINT,
    BrokerAdmissionError,
    GroqBrokerPolicy,
    GroqLocalBroker,
    read_groq_key,
)

MARKER = "ROS_SYNTHETIC_TASK_346_BOUND"


@pytest.fixture()
def mock_groq(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "text/event-stream"}

        def __init__(self):
            self.raw = io.BytesIO(b"data: {\"choices\": []}\n\ndata: [DONE]\n\n")

        def read1(self, n):
            return self.raw.read(n)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    requests = []

    def fake_open(opener, request, *, timeout):
        assert request.full_url == GROQ_ENDPOINT
        assert "gsk_" in request.headers["Authorization"]
        assert not any("gsk_" in key for key in request.headers if key != "Authorization")
        assert timeout <= 55
        requests.append(json.loads(request.data))
        return Response()

    monkeypatch.setattr("urllib.request.OpenerDirector.open", fake_open)
    return requests


@pytest.fixture()
def broker(tmp_path):
    parent = tmp_path / "sock"
    parent.mkdir(mode=0o700)
    policy = GroqBrokerPolicy(task_id="TASK-346", task_marker=MARKER, max_requests=2)
    with GroqLocalBroker(socket_path=parent / "groq.sock", policy=policy,
                             api_key="gsk_" + "T" * 32) as server:
        yield server


def request(broker, method="POST", path="/openai/v1/chat/completions", body=None):
    if body is None:
        body = {"model": "openai/gpt-oss-120b", "stream": True,
                "messages": [{"role": "user", "content": MARKER + " add two numbers"}]}
    raw = json.dumps(body).encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        sock.connect(str(broker.socket_path))
        message = (
            f"{method} {path} HTTP/1.0\r\n"
            f"Host: local\r\nContent-Length: {len(raw)}\r\n\r\n"
        )
        sock.sendall(message.encode() + raw)
        payload = b""
        while data := sock.recv(65536):
            payload += data
    header, _, body_out = payload.partition(b"\r\n\r\n")
    return int(header.split(b" ")[1]), body_out


def test_forwards_only_fixed_model_and_rewrites_budget(mock_groq, broker):
    status, payload = request(broker)
    assert status == 200 and b"[DONE]" in payload
    assert len(mock_groq) == 1
    assert mock_groq[0]["model"] == "openai/gpt-oss-120b"
    assert mock_groq[0]["reasoning_effort"] == "low"
    assert mock_groq[0]["max_completion_tokens"] == 1024
    assert mock_groq[0]["parallel_tool_calls"] is False
    assert broker.evidence.upstream_statuses == [200]


def test_extra_request_is_denied_before_upstream(mock_groq, broker):
    assert request(broker)[0] == 200
    assert request(broker)[0] == 200
    assert request(broker)[0] == 429
    assert len(mock_groq) == 2 and broker.evidence.denied == 1


@pytest.mark.parametrize("invalid,code", [
    ({"model": "evil", "messages": [{"role": "user", "content": MARKER}]}, 403),
    ({"model": "openai/gpt-oss-120b",
      "messages": [{"role": "user", "content": "other task"}]}, 403),
    ({"model": "openai/gpt-oss-120b", "messages": []}, 400),
    ({"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": MARKER}],
      "functions": [{"name": "arbitrary"}]}, 403),
])
def test_rejects_untrusted_model_task_and_tool_transport(mock_groq, broker, invalid, code):
    assert request(broker, body=invalid)[0] == code
    assert not mock_groq


def test_endpoint_and_health_never_charge_quota(mock_groq, broker):
    assert request(broker, "GET", "/health")[0] == 200
    assert request(broker, "POST", "/admin")[0] == 403
    assert request(broker, "GET", "/private")[0] == 404
    assert broker.evidence.attempts == 0 and not mock_groq


def test_health_client_disconnect_is_not_uncaught(broker):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(broker.socket_path))
        sock.sendall(b"GET /health HTTP/1.0\r\nHost: local\r\n\r\n")
    assert request(broker, "GET", "/health")[0] == 200




def test_health_disconnect_during_headers_is_bounded(broker, monkeypatch):
    """Disconnected health probes must not generate server thread tracebacks."""
    entered = threading.Event()
    unexpected_error = threading.Event()
    original_end_headers = BaseHTTPRequestHandler.end_headers

    def simulate_disconnect_during_headers(self):
        entered.set()
        raise BrokenPipeError("client closed before response headers")

    def observe_unhandled_exception(self, request, client_address):
        unexpected_error.set()

    monkeypatch.setattr(
        BaseHTTPRequestHandler, "end_headers", simulate_disconnect_during_headers
    )
    monkeypatch.setattr(broker._server, "handle_error", observe_unhandled_exception)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(broker.socket_path))
        sock.sendall(b"GET /health HTTP/1.0\r\nHost: local\r\n\r\n")
        assert entered.wait(2)
        assert sock.recv(1024) == b""
    assert not unexpected_error.is_set()
    assert not broker.evidence.client_disconnected
    monkeypatch.setattr(BaseHTTPRequestHandler, "end_headers", original_end_headers)


def test_post_disconnect_during_headers_marks_evidence(broker, monkeypatch):
    """A failed POST response is not valid independent provider evidence."""
    entered = threading.Event()
    original_end_headers = BaseHTTPRequestHandler.end_headers

    def simulate_disconnect_during_headers(self):
        entered.set()
        raise BrokenPipeError("client closed before response headers")

    monkeypatch.setattr(
        BaseHTTPRequestHandler, "end_headers", simulate_disconnect_during_headers
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(broker.socket_path))
        sock.sendall(b"POST /admin HTTP/1.0\r\nHost: local\r\nContent-Length: 0\r\n\r\n")
        assert entered.wait(2)
        assert sock.recv(1024) == b""
    assert broker.evidence.client_disconnected
    monkeypatch.setattr(BaseHTTPRequestHandler, "end_headers", original_end_headers)

def test_invalid_policy_fail_closed():
    with pytest.raises(BrokerAdmissionError, match="request cap"):
        GroqBrokerPolicy(task_id="test", task_marker=MARKER, max_requests=1000)
    with pytest.raises(BrokerAdmissionError, match="unsupported"):
        GroqBrokerPolicy(task_id="test", task_marker=MARKER, model="other")
    with pytest.raises(BrokerAdmissionError, match="token cap"):
        GroqBrokerPolicy(task_id="test", task_marker=MARKER, max_completion_tokens=5000)


def test_socket_requires_host_private_directory(tmp_path):
    public = tmp_path / "public"
    public.mkdir(mode=0o777)
    public.chmod(0o777)
    policy = GroqBrokerPolicy(task_id="TASK", task_marker=MARKER)
    with pytest.raises(BrokerAdmissionError, match="private"):
        with GroqLocalBroker(socket_path=public / "groq.sock", policy=policy,
                             api_key="gsk_" + "K" * 32):
            pass


def test_socket_cleanup_drops_key(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    path = folder / "sock"
    server = GroqLocalBroker(socket_path=path,
                             policy=GroqBrokerPolicy(task_id="x", task_marker=MARKER),
                             api_key="gsk_" + "A" * 32)
    with server:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not path.exists()
    assert server._key == ""


def test_local_credential_permissions_and_no_symlink(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"groq": {"type": "api", "key": "gsk_" + "D" * 32}}))
    auth.chmod(0o600)
    assert read_groq_key(auth).startswith("gsk_")
    auth.chmod(0o644)
    with pytest.raises(BrokerAdmissionError):
        read_groq_key(auth)
    auth.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(auth)
    with pytest.raises(OSError):
        read_groq_key(link)


def test_post_budget_atomic_concurrency(mock_groq, broker):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: request(broker)[0], range(8)))
    assert statuses.count(200) == 2
    assert statuses.count(429) == 6
    assert len(mock_groq) == 2


def test_prior_success_cannot_mask_wrong_upstream_content_type(
    mock_groq, broker, monkeypatch,
):
    assert request(broker)[0] == 200

    class WrongType:
        status = 200
        headers = {"Content-Type": "application/octet-stream"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr("urllib.request.OpenerDirector.open",
                        lambda *_args, **_kwargs: WrongType())
    assert request(broker)[0] == 502
    assert broker.evidence.attempts == 2
    assert broker.evidence.upstream_statuses == [200, 200]
    assert broker.evidence.response_bytes > 0
    assert broker.evidence.upstream_incomplete


@pytest.mark.parametrize("failure", ["exception", "empty", "truncated"])
def test_later_incomplete_upstream_cannot_count_as_success(
    mock_groq, broker, monkeypatch, failure,
):
    assert request(broker)[0] == 200

    class IncompleteStream:
        status = 200
        headers = {"Content-Type": "text/event-stream"}

        def __init__(self):
            self.emitted = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read1(self, _size):
            if failure == "exception":
                raise TimeoutError("synthetic provider stream interruption")
            if failure == "truncated" and not self.emitted:
                self.emitted = True
                return b'data: {"choices": [{"delta": {"content": "partial"}}]}\n\n'
            return b""

    monkeypatch.setattr("urllib.request.OpenerDirector.open",
                        lambda *_args, **_kwargs: IncompleteStream())
    status, payload = request(broker)
    assert status == 200
    assert b"HTTP/1.0 502" not in payload
    assert broker.evidence.attempts == 2
    assert broker.evidence.upstream_statuses == [200, 200]
    assert broker.evidence.response_bytes > 0
    assert broker.evidence.upstream_incomplete


@pytest.mark.parametrize("response_type,body,complete", [
    ("text/event-stream", b'data: {"choices": []}\n\ndata: [DONE]\n\n', True),
    ("application/json", b'{"choices": [{"message": {"content": "ok"}}]}', True),
    ("application/json", b'{"choices": [{', False),
    ("application/json", b'{"error": "provider failed"}', False),
])
def test_upstream_requires_complete_chat_response(
    broker, monkeypatch, response_type, body, complete,
):
    class MockCompletion:
        status = 200
        headers = {"Content-Type": response_type}

        def __init__(self):
            # Deliberately split terminal SSE marker across reads.
            half = max(1, len(body) - 5)
            self.chunks = [body[:half], body[half:]]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read1(self, _size):
            return self.chunks.pop(0) if self.chunks else b""

    monkeypatch.setattr("urllib.request.OpenerDirector.open",
                        lambda *_args, **_kwargs: MockCompletion())
    status, _ = request(broker)
    assert status == 200
    assert broker.evidence.attempts == 1
    assert broker.evidence.upstream_statuses == [200]
    assert broker.evidence.upstream_incomplete is (not complete)
