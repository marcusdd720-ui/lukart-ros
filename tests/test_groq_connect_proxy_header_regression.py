"""P0 CONNECT-header fail-closed regression. Only local loopback sockets.

Proves both HTTP rejection AND zero upstream-connection attempts. Does not
exercise Docker networking, TLS, external DNS or a real Groq connection.
No third-party dependencies; run with python -m unittest.
"""
from __future__ import annotations

import importlib.util
import os
import select
import socket
import socketserver
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SOURCE = Path(os.environ.get(
    "A2_PROXY_SOURCE", Path(__file__).resolve().parents[1] / "scripts" / "groq_connect_proxy.py"
))


def load_proxy():
    spec = importlib.util.spec_from_file_location("a2_connect_proxy_under_test", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Missing test subject: {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            while data := self.request.recv(65536):
                self.request.sendall(data)
        except OSError:
            return


class LoopbackServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TestConnectHeaderP0(unittest.TestCase):
    def setUp(self):
        self.proxy = load_proxy()
        self.attempts: list[tuple[str, int]] = []
        self.echo = LoopbackServer(("127.0.0.1", 0), Echo)
        self.echo_thread = threading.Thread(target=self.echo.serve_forever, daemon=True)
        self.echo_thread.start()
        self.target = self.echo.server_address

        def upstream_connect(destination, timeout=None, *args, **kwargs):
            self.attempts.append(destination)
            if destination != ("api.groq.com", 443):
                raise AssertionError("Non-allowlisted upstream requested")
            # Redirect the permitted destination to a local synthetic echo.
            # No DNS lookup or real Internet/provider connection is possible.
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(timeout or 3)
            upstream.connect(self.target)
            return upstream

        self.upstream_patch = mock.patch.object(
            self.proxy.socket, "create_connection", side_effect=upstream_connect
        )
        self.upstream_patch.start()
        self.server = self.proxy._Proxy(("127.0.0.1", 0), self.proxy._ConnectHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.proxy_addr = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.upstream_patch.stop()
        self.echo.shutdown()
        self.echo.server_close()
        self.echo_thread.join(timeout=2)

    def exchange(self, payload, *, half_close=False, echo_payload=None):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(4)
            client.connect(self.proxy_addr)
            client.sendall(payload)
            if half_close:
                client.shutdown(socket.SHUT_WR)
            try:
                response = client.recv(256)
            except TimeoutError:
                response = b""
            if echo_payload is None:
                return response, b""
            if not response.startswith(b"HTTP/1.1 200 "):
                return response, b""
            client.sendall(echo_payload)
            received = bytearray()
            while len(received) < len(echo_payload):
                part = client.recv(65536)
                if not part:
                    break
                received.extend(part)
            return response, bytes(received)

    def reject_without_upstream(self, payload, *, half_close=False):
        response, _ = self.exchange(payload, half_close=half_close)
        self.assertTrue(
            response.startswith(b"HTTP/1.1 403 Forbidden\r\n"),
            f"Expected HTTP 403, got {response!r} (attempts={self.attempts!r})",
        )
        self.assertEqual(self.attempts, [], "Blocked request attempted upstream connection")

    def test_01_incomplete_max_header_is_403_and_zero_upstream(self):
        first = b"CONNECT api.groq.com:443 HTTP/1.1\r\n"
        # Exactly MAX_HEADER bytes; valid first line but no CRLFCRLF.
        data = first + b"X:" + b"a" * (self.proxy.MAX_HEADER - len(first) - 4) + b"\r\n"
        self.assertEqual(len(data), self.proxy.MAX_HEADER)
        self.assertNotIn(b"\r\n\r\n", data)
        self.reject_without_upstream(data)

    def test_02_incomplete_header_on_half_close_is_403_and_zero_upstream(self):
        data = b"CONNECT api.groq.com:443 HTTP/1.1\r\nHost: api.groq.com:443\r\n"
        self.reject_without_upstream(data, half_close=True)

    def test_03_disallowed_authority_is_403_and_zero_upstream(self):
        self.reject_without_upstream(b"CONNECT example.org:443 HTTP/1.1\r\n\r\n")

    def test_04_disallowed_port_is_403_and_zero_upstream(self):
        self.reject_without_upstream(b"CONNECT api.groq.com:80 HTTP/1.1\r\n\r\n")

    def test_05_valid_complete_header_relays_only_to_loopback(self):
        payload = bytes(range(256)) * 64
        response, echoed = self.exchange(
            b"CONNECT api.groq.com:443 HTTP/1.1\r\n\r\n",
            echo_payload=payload,
        )
        self.assertTrue(response.startswith(b"HTTP/1.1 200 Connection Established"), response)
        self.assertEqual(echoed, payload)
        self.assertEqual(self.attempts, [("api.groq.com", 443)])

    def test_06_exact_max_header_with_terminator_is_allowed(self):
        first = b"CONNECT api.groq.com:443 HTTP/1.1\r\n"
        data = first + b"X:" + b"a" * (self.proxy.MAX_HEADER - len(first) - 6) + b"\r\n\r\n"
        self.assertEqual(len(data), self.proxy.MAX_HEADER)
        response, _ = self.exchange(data)
        self.assertTrue(response.startswith(b"HTTP/1.1 200 Connection Established"), response)
        self.assertEqual(self.attempts, [("api.groq.com", 443)])

    def test_07_slow_incomplete_header_has_total_deadline(self):
        # Repeated bytes within the receive timeout cannot reset total deadline.
        self.proxy.HEADER_DEADLINE_SECONDS = 0.5
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(self.proxy_addr)
            client.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\nX: ")
            start = time.monotonic()
            response = b""
            # Keep sending before each hypothetical per-recv idle timeout. A
            # regressed handler without a total deadline never replies here.
            while time.monotonic() - start < 1.3:
                readable, _, _ = select.select([client], [], [], 0.075)
                if readable:
                    response = client.recv(256)
                    break
                client.sendall(b"x")
            elapsed = time.monotonic() - start
        self.assertTrue(response.startswith(b"HTTP/1.1 403 Forbidden"), response)
        self.assertLess(elapsed, 1.05, "Total header deadline reset by trickle bytes")
        self.assertEqual(self.attempts, [])

    def test_08_connections_over_quota_are_refused(self):
        # Replace the semaphore only on this empty fixture server; do not
        # attempt mass connection / resource exhaustion.
        self.server._slots = threading.BoundedSemaphore(2)
        clients = []
        try:
            for _ in range(2):
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(2)
                client.connect(self.proxy_addr)
                client.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\nX: ")
                clients.append(client)
                time.sleep(0.12)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as extra:
                extra.settimeout(2)
                extra.connect(self.proxy_addr)
                extra.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\nX: ")
                try:
                    refusal = extra.recv(256)
                except ConnectionResetError:
                    refusal = b""  # Closing a socket with unread data can send TCP RST.
                except ConnectionAbortedError as exc:
                    # Windows can report WSAECONNABORTED when a rejected socket
                    # is closed with unread request data. Only that exact case.
                    if getattr(exc, "winerror", None) != 10053:
                        raise
                    refusal = b""
                self.assertEqual(refusal, b"", "Over-quota client not refused")
            for client in clients:
                client.shutdown(socket.SHUT_WR)
                self.assertTrue(client.recv(256).startswith(b"HTTP/1.1 403"))
            self.assertEqual(self.attempts, [])
        finally:
            for client in clients:
                client.close()

    def test_09_idle_established_tunnel_has_total_lifetime(self):
        # Tests total tunnel lifetime without any external DNS/provider.
        self.proxy.TUNNEL_LIFETIME_SECONDS = 0.65
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(self.proxy_addr)
            client.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\n\r\n")
            self.assertTrue(client.recv(256).startswith(b"HTTP/1.1 200"))
            self.assertEqual(client.recv(256), b"", "Idle tunnel outlived total deadline")
        self.assertEqual(self.attempts, [("api.groq.com", 443)])

    def test_10_active_relay_sendall_gets_remaining_deadline(self):
        # Simulate backpressure without external traffic or large allocations.
        self.proxy.TUNNEL_LIFETIME_SECONDS = 0.75
        original_sendall = socket.socket.sendall
        observed: list[float] = []

        def observe_sendall(sock, data, *args, **kwargs):
            try:
                is_upstream = sock.getpeername() == self.target
            except OSError:
                is_upstream = False
            if is_upstream:
                timeout = sock.gettimeout()
                assert timeout is not None
                observed.append(timeout)
                # Model a receiver that cannot drain before the socket timeout.
                raise TimeoutError("synthetic upstream backpressure")
            return original_sendall(sock, data, *args, **kwargs)

        with mock.patch.object(socket.socket, "sendall", observe_sendall):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(self.proxy_addr)
                client.sendall(b"CONNECT api.groq.com:443 HTTP/1.1\r\n\r\n")
                self.assertTrue(client.recv(256).startswith(b"HTTP/1.1 200"))
                time.sleep(0.25)
                client.sendall(b"active tunnel payload")
                self.assertEqual(client.recv(256), b"")
        self.assertEqual(len(observed), 1)
        self.assertLess(observed[0], 0.75, "sendall retained fixed 15s timeout")
        self.assertGreater(observed[0], 0)
        self.assertEqual(self.attempts, [("api.groq.com", 443)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
