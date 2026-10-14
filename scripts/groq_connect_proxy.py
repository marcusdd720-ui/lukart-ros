"""Small deny-by-default CONNECT proxy for a disposable Groq-only test.

Only api.groq.com:443 is reachable through this proxy. It must run in a
separate dual-homed container; the worker itself needs an internal-only
Docker network. This does not attest provider billing or independent review.
"""
from __future__ import annotations

import select
import socket
import socketserver
import threading
import time

ALLOWED_HOST = "api.groq.com"
ALLOWED_PORT = 443
MAX_HEADER = 4096
HEADER_DEADLINE_SECONDS = 5
TUNNEL_LIFETIME_SECONDS = 120
MAX_ACTIVE_CLIENTS = 16  # Below the proxy container pids-limit 32


class _ConnectHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(5)
        header = bytearray()
        deadline = time.monotonic() + HEADER_DEADLINE_SECONDS
        try:
            while b"\r\n\r\n" not in header and len(header) < MAX_HEADER:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.request.settimeout(remaining)
                chunk = self.request.recv(1)
                if not chunk:
                    break
                header.extend(chunk)
        except TimeoutError:
            pass
        if b"\r\n\r\n" not in header:
            # Never connect upstream until a complete CONNECT header is seen.
            try:
                self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            return
        first = bytes(header).split(b"\r\n", 1)[0]
        if first != b"CONNECT api.groq.com:443 HTTP/1.1":
            self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((ALLOWED_HOST, ALLOWED_PORT), 5)
        except OSError:
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            return
        with upstream:
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            # Keep sockets blocking: sendall() must forward each whole chunk.
            # Bounded timeouts fail closed if the peer stops accepting data.
            upstream.settimeout(15)
            self.request.settimeout(15)
            sockets = [self.request, upstream]
            tunnel_deadline = time.monotonic() + TUNNEL_LIFETIME_SECONDS
            while True:
                try:
                    remaining = tunnel_deadline - time.monotonic()
                    if remaining <= 0:
                        return
                    readable, _, _ = select.select(sockets, [], [], min(15, remaining))
                    if not readable:
                        return
                    for source in readable:
                        # Both recv and sendall must respect the one tunnel deadline.
                        remaining = tunnel_deadline - time.monotonic()
                        if remaining <= 0:
                            return
                        source.settimeout(min(15, remaining))
                        data = source.recv(65536)
                        if not data:
                            return
                        remaining = tunnel_deadline - time.monotonic()
                        if remaining <= 0:
                            return
                        destination = upstream if source is self.request else self.request
                        destination.settimeout(min(15, remaining))
                        destination.sendall(data)
                except OSError:
                    return


class _Proxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._slots = threading.BoundedSemaphore(MAX_ACTIVE_CLIENTS)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            request.close()  # Fail closed instead of spawning an unbounded thread.
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


if __name__ == "__main__":
    with _Proxy(("0.0.0.0", 8080), _ConnectHandler) as server:
        server.serve_forever(poll_interval=0.1)
