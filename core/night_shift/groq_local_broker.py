"""Host-only, fixed-destination Groq gateway for fenced Night Shift workers.

This is a *capability*, not a task dispatcher or an execution admission decision.
The caller must separately establish an approved exact task, isolated worktree,
verified OS sandbox, and ChildProcessBridge admission. No secret enters the child.
"""

from __future__ import annotations

import json
import os
import socketserver
import ssl
import stat
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"


class BrokerAdmissionError(ValueError):
    """Fail-closed invalid local broker authority or request."""


@dataclass(frozen=True, slots=True)
class GroqBrokerPolicy:
    """Trusted host parameters. Never construct from model-supplied data."""

    task_id: str
    task_marker: str
    model: str = GROQ_MODEL
    max_requests: int = 3
    max_input_bytes: int = 65536
    max_output_bytes: int = 524288
    max_completion_tokens: int = 1024
    upstream_timeout_seconds: int = 55

    def __post_init__(self) -> None:
        if (not self.task_id.strip() or not self.task_marker.strip()
                or len(self.task_marker) < 16 or len(self.task_marker) > 256):
            raise BrokerAdmissionError("explicit task identity and marker required")
        if self.model != GROQ_MODEL:
            raise BrokerAdmissionError("unsupported provider/model")
        if not (1 <= self.max_requests <= 3):
            raise BrokerAdmissionError("request cap must be 1..3")
        if not (1 <= self.max_input_bytes <= 65536):
            raise BrokerAdmissionError("invalid request byte cap")
        if not (1 <= self.max_output_bytes <= 524288):
            raise BrokerAdmissionError("invalid response byte cap")
        if not (1 <= self.max_completion_tokens <= 1024):
            raise BrokerAdmissionError("invalid token cap")
        if not (1 <= self.upstream_timeout_seconds <= 55):
            raise BrokerAdmissionError("invalid provider timeout")


def read_groq_key(auth_file: Path) -> str:
    """Load a local OpenCode credential without symlinks or ambient key export."""
    fd = os.open(auth_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_size > 16384):
            raise BrokerAdmissionError("local credential ownership/permissions invalid")
        raw = os.read(fd, 16385)
    finally:
        os.close(fd)
    if len(raw) > 16384:
        raise BrokerAdmissionError("oversized credential")
    obj = json.loads(raw)
    credential = obj.get("groq") if isinstance(obj, dict) else None
    if not isinstance(credential, dict) or credential.get("type") not in {"api", "api_key"}:
        raise BrokerAdmissionError("Groq credential missing")
    key = credential.get("key")
    if not isinstance(key, str) or not key.startswith("gsk_") or not 20 <= len(key) <= 512:
        raise BrokerAdmissionError("Groq credential is invalid")
    return key


@dataclass(slots=True)
class BrokerEvidence:
    attempts: int = 0
    denied: int = 0
    upstream_statuses: list[int] = field(default_factory=list)
    response_bytes: int = 0
    response_overflow: bool = False
    client_disconnected: bool = False
    upstream_incomplete: bool = False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


class _UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False
    # Backlog is bounded but must accept simultaneous local callers so that
    # the atomic policy limit, not an incidental kernel accept race, decides.
    request_queue_size = 16


class GroqLocalBroker:
    """Bounded Unix-socket server with a single fixed HTTPS upstream.

    The socket directory MUST be host-owned, private (0700), and outside the
    worker's writable mounts; the isolated worker may see only the socket.
    """

    def __init__(self, *, socket_path: Path, policy: GroqBrokerPolicy, api_key: str) -> None:
        if not api_key.startswith("gsk_") or len(api_key) < 20:
            raise BrokerAdmissionError("missing provider credential")
        self.socket_path = socket_path
        self.policy = policy
        self._key = api_key
        self.evidence = BrokerEvidence()
        self._lock = threading.Lock()
        self._server: _UnixServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> GroqLocalBroker:
        parent = self.socket_path.parent
        info = parent.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or self.socket_path.exists()
                or self.socket_path.is_symlink()):
            raise BrokerAdmissionError("private unused host-owned socket directory required")
        broker = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args: Any) -> None:
                pass  # Never log prompt, credentials, or upstream responses.

            def reply(self, code: int, message: str) -> None:
                data = (message + "\n").encode("ascii")
                try:
                    # A client can disconnect while headers are being sent,
                    # before the body write begins. Both stages are fallible.
                    self.send_response(code)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    # A health probe may deliberately close after reading status.
                    # A POST disconnect, unlike a health probe, invalidates evidence.
                    if self.command == "POST":
                        with broker._lock:
                            broker.evidence.client_disconnected = True

            def do_GET(self) -> None:
                self.reply(200, "OK") if self.path == "/health" else self.reply(404, "NOT_FOUND")

            def do_POST(self) -> None:
                if self.path != "/openai/v1/chat/completions":
                    return self.reply(403, "ENDPOINT_DENIED")
                if self.headers.get("Transfer-Encoding"):
                    return self.reply(400, "CHUNKED_DENIED")
                try:
                    size = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    return self.reply(400, "INVALID_LENGTH")
                if not 0 < size <= broker.policy.max_input_bytes:
                    return self.reply(413, "REQUEST_SIZE_DENIED")
                with broker._lock:
                    exhausted = broker.evidence.attempts >= broker.policy.max_requests
                    if exhausted:
                        broker.evidence.denied += 1
                    else:
                        broker.evidence.attempts += 1
                if exhausted:
                    return self.reply(429, "REQUEST_BUDGET_EXHAUSTED")
                headers_started = False
                try:
                    request = json.loads(self.rfile.read(size))
                    if not isinstance(request, dict) or request.get("model") != GROQ_MODEL:
                        return self.reply(403, "MODEL_DENIED")
                    messages = request.get("messages")
                    if not isinstance(messages, list) or not messages:
                        return self.reply(400, "MESSAGES_REQUIRED")
                    # Marker is a scoping check, NOT cryptographic authorization.
                    if not any(isinstance(m, dict) and m.get("role") == "user"
                               and broker.policy.task_marker in json.dumps(m.get("content", ""))
                               for m in messages):
                        return self.reply(403, "TASK_MARKER_MISSING")
                    if any(field in request for field in (
                        "functions", "function_call", "tools", "tool_choice"
                    )):
                        return self.reply(403, "UNSUPPORTED_TOOL_TRANSPORT")
                    request["max_completion_tokens"] = broker.policy.max_completion_tokens
                    request["reasoning_effort"] = "low"
                    request["parallel_tool_calls"] = False
                    request.pop("max_tokens", None)
                    encoded = json.dumps(request, separators=(",", ":")).encode()
                    if len(encoded) > broker.policy.max_input_bytes:
                        return self.reply(413, "ENCODED_SIZE_DENIED")
                    outbound = urllib.request.Request(
                        GROQ_ENDPOINT, encoded,
                        {"Authorization": "Bearer " + broker._key,
                         "Content-Type": "application/json",
                         "Accept": "text/event-stream, application/json",
                         "User-Agent": "lukart-ros-local-groq-broker/1"}, method="POST")
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({}), _NoRedirect(),
                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
                    try:
                        response = opener.open(
                            outbound, timeout=broker.policy.upstream_timeout_seconds
                        )
                    except urllib.error.HTTPError as exc:
                        with broker._lock:
                            broker.evidence.upstream_statuses.append(exc.code)
                        return self.reply(502, "PROVIDER_HTTP_ERROR")
                    with response:
                        with broker._lock:
                            broker.evidence.upstream_statuses.append(response.status)
                        ctype = response.headers.get("Content-Type", "")
                        if not (
                            ctype.startswith("text/event-stream")
                            or ctype.startswith("application/json")
                        ):
                            with broker._lock:
                                broker.evidence.upstream_incomplete = True
                            return self.reply(502, "PROVIDER_CONTENT_TYPE_DENIED")
                        # A partially sent 200 response must never receive a second HTTP status line.
                        headers_started = True
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        got_bytes = False
                        while chunk := response.read1(4096):
                            got_bytes = True
                            with broker._lock:
                                if (
                                    broker.evidence.response_bytes + len(chunk)
                                    > broker.policy.max_output_bytes
                                ):
                                    broker.evidence.response_overflow = True
                                    return
                                broker.evidence.response_bytes += len(chunk)
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        if not got_bytes:
                            with broker._lock:
                                broker.evidence.upstream_incomplete = True
                except (BrokenPipeError, ConnectionResetError):
                    with broker._lock:
                        broker.evidence.client_disconnected = True
                        broker.evidence.upstream_incomplete = True
                except (OSError, ValueError, urllib.error.URLError, TimeoutError):
                    with broker._lock:
                        broker.evidence.upstream_incomplete = True
                    if not headers_started:
                        self.reply(502, "PROVIDER_CONNECTIVITY_ERROR")

        self._server = _UnixServer(str(self.socket_path), Handler)
        os.chmod(self.socket_path, 0o600)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        try:
            if self._server is not None:
                self._server.shutdown()
                self._server.server_close()
            if self._thread is not None:
                self._thread.join(timeout=3)
        finally:
            self._key = ""
            self.socket_path.unlink(missing_ok=True)
