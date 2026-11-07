"""A minimal injectable HTTP layer over urllib, so destination and source clients
can be tested with fakes. No retries, no translation logic."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 30.0


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class HttpTransportError(Exception):
    """The request may or may not have reached the server (timeout, reset, DNS, ...)."""


HttpSend = Callable[[HttpRequest], HttpResponse]


def urllib_send(req: HttpRequest) -> HttpResponse:
    """Default transport. Every HTTP status becomes an HttpResponse; anything else
    (timeouts, connection errors) becomes HttpTransportError."""
    request = urllib.request.Request(
        req.url, data=req.body, headers=dict(req.headers), method=req.method
    )
    try:
        with urllib.request.urlopen(request, timeout=req.timeout) as resp:  # noqa: S310
            return HttpResponse(status=resp.status, body=resp.read())
    except urllib.error.HTTPError as err:
        return HttpResponse(status=err.code, body=err.read())
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        reason = getattr(err, "reason", err)
        raise HttpTransportError(f"{type(err).__name__}: {reason}") from err
