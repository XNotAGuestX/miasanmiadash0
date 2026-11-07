"""urllib_send against a real local server: truncation and redirects."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import cast

import pytest

from migrator.destination.dash0 import Dash0Config, Unknown, publish_dashboard
from migrator.http import HttpRequest, HttpTransportError, urllib_send
from migrator.target import PersesDashboard

DASHBOARD = cast(PersesDashboard, {"kind": "Dashboard", "metadata": {"name": "d"}, "spec": {}})
Handler = Callable[[socket.socket], None]


@contextmanager
def raw_server(handle: Handler) -> Iterator[str]:
    """Serve one connection with a hand-written HTTP response."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def run() -> None:
        conn, _ = srv.accept()
        with conn:
            conn.recv(65536)
            handle(conn)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        thread.join(timeout=5)
        srv.close()


def truncated(status: int) -> Handler:
    def handle(conn: socket.socket) -> None:
        conn.sendall(
            f"HTTP/1.1 {status} X\r\nContent-Length: 100\r\nConnection: close\r\n\r\n"
            '{"met'.encode()
        )

    return handle


def test_truncated_2xx_body_is_a_transport_error() -> None:
    with raw_server(truncated(200)) as url, pytest.raises(HttpTransportError) as exc:
        urllib_send(HttpRequest("POST", url, body=b"{}", timeout=5))
    assert "IncompleteRead" in str(exc.value)


def test_truncated_error_body_is_a_transport_error() -> None:
    with raw_server(truncated(500)) as url, pytest.raises(HttpTransportError):
        urllib_send(HttpRequest("GET", url, timeout=5))


def test_truncated_import_response_is_unknown() -> None:
    with raw_server(truncated(200)) as url:
        cfg = Dash0Config(api_url=url, token="tok", dataset="default")
        out = publish_dashboard(DASHBOARD, cfg)
    assert isinstance(out, Unknown)


def test_redirect_is_not_followed() -> None:
    def handle(conn: socket.socket) -> None:
        conn.sendall(
            b"HTTP/1.1 302 Found\r\nLocation: http://example.invalid/x\r\n"
            b"Content-Length: 0\r\nConnection: close\r\n\r\n"
        )

    with raw_server(handle) as url:
        resp = urllib_send(
            HttpRequest("POST", url, headers={"Authorization": "Bearer t"}, body=b"{}")
        )
    assert resp.status == 302
    assert not resp.ok
