"""Dash0 HTTP client: import and read-back only. No translation logic here.

Create-only: never sends metadata.dash0Extensions or a check-rule id. No retries.
An ambiguous result (transport error, any 5xx, a 2xx without an id) is "unknown",
which the receipts (07.T3) refuse to republish.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote, urlsplit

from migrator.http import (
    HttpRequest,
    HttpResponse,
    HttpSend,
    HttpTransportError,
    urllib_send,
)
from migrator.input import InputError
from migrator.target import Dash0CheckRule, PersesDashboard

# UNVERIFIED until plan 07 Task 1: where the new ID sits in each import response.
DASHBOARD_ID_PATH: tuple[str, ...] = ("metadata", "dash0Extensions", "id")
# UNVERIFIED until plan 07 Task 1.
CHECK_RULE_ID_PATH: tuple[str, ...] = ("id",)

REQUEST_TIMEOUT_S = 30.0
MESSAGE_MAX = 500
# A 5xx means the request reached a server (Dash0 or a proxy in front of it) that
# then failed; Dash0 may already have created the asset. Only a 4xx is a definite
# rejection that created nothing, so only a 4xx may be republished.
AMBIGUOUS_STATUS_MIN = 500
_ENV_NAMES = ("DASH0_API_URL", "DASH0_AUTH_TOKEN", "DASH0_DATASET")

ImportKind = Literal["dashboard", "check-rule"]


@dataclass(frozen=True)
class Dash0Config:
    api_url: str
    token: str
    dataset: str


@dataclass(frozen=True)
class Imported:
    id: str
    http_status: int
    status: Literal["imported"] = "imported"


@dataclass(frozen=True)
class Failed:
    http_status: int
    message: str
    status: Literal["failed"] = "failed"


@dataclass(frozen=True)
class Unknown:
    message: str
    status: Literal["unknown"] = "unknown"


PublishOutcome = Imported | Failed | Unknown


def read_dash0_config(env: Mapping[str, str | None]) -> Dash0Config:
    """Raise InputError("missing env: A, B") naming only the variables, never their values."""
    missing = [name for name in _ENV_NAMES if not (env.get(name) or "").strip()]
    if missing:
        raise InputError(f"missing env: {', '.join(missing)}")
    api_url = (env["DASH0_API_URL"] or "").strip().rstrip("/")
    parts = urlsplit(api_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise InputError("DASH0_API_URL must be an http(s) URL")
    return Dash0Config(
        api_url=api_url,
        token=(env["DASH0_AUTH_TOKEN"] or "").strip(),
        dataset=(env["DASH0_DATASET"] or "").strip(),
    )


def _redact(text: str, token: str) -> str:
    return text.replace(token, "<redacted>") if token else text


def _clip(text: str, token: str) -> str:
    return _redact(text, token)[:MESSAGE_MAX]


def _url(cfg: Dash0Config, path: str) -> str:
    return f"{cfg.api_url}{path}?dataset={quote(cfg.dataset, safe='')}"


def _headers(cfg: Dash0Config, with_body: bool) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {cfg.token}", "Accept": "application/json"}
    if with_body:
        headers["Content-Type"] = "application/json"
    return headers


def _dig(value: Any, path: tuple[str, ...]) -> Any:
    cur = value
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _post_import(
    kind: ImportKind,
    body: Mapping[str, Any],
    id_path: tuple[str, ...],
    cfg: Dash0Config,
    send: HttpSend,
) -> PublishOutcome:
    request = HttpRequest(
        method="POST",
        url=_url(cfg, f"/api/import/{kind}"),
        headers=_headers(cfg, with_body=True),
        body=json.dumps(body).encode("utf-8"),
        timeout=REQUEST_TIMEOUT_S,
    )
    try:
        response: HttpResponse = send(request)
    except HttpTransportError as err:
        # The request may have reached Dash0; never assume it didn't.
        return Unknown(_clip(f"{err}; the {kind} may or may not exist in Dash0", cfg.token))

    text = _decode(response.body)
    if response.status >= AMBIGUOUS_STATUS_MIN:
        return Unknown(
            _clip(
                f"HTTP {response.status} (server error); the {kind} may or may not exist "
                f"in Dash0: {text}",
                cfg.token,
            )
        )
    if not response.ok:
        return Failed(http_status=response.status, message=_clip(text, cfg.token))

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return Unknown(_clip(f"HTTP {response.status} with a non-JSON body: {text}", cfg.token))
    new_id = _dig(parsed, id_path)
    if not isinstance(new_id, str) or not new_id:
        return Unknown(
            f"HTTP {response.status} but no id at {'.'.join(id_path)}; the {kind} was "
            "probably created, reconcile before republishing"
        )
    return Imported(id=new_id, http_status=response.status)


def publish_dashboard(
    body: PersesDashboard, cfg: Dash0Config, send: HttpSend = urllib_send
) -> PublishOutcome:
    metadata = body.get("metadata")
    if isinstance(metadata, dict) and "dash0Extensions" in metadata:
        raise InputError(
            "refusing to publish a dashboard with metadata.dash0Extensions (create-only)"
        )
    return _post_import("dashboard", body, DASHBOARD_ID_PATH, cfg, send)


def publish_check_rule(
    body: Dash0CheckRule, cfg: Dash0Config, send: HttpSend = urllib_send
) -> PublishOutcome:
    if "id" in body:
        raise InputError("refusing to publish a check rule with an id (create-only)")
    return _post_import("check-rule", body, CHECK_RULE_ID_PATH, cfg, send)


def read_back(
    kind: ImportKind, asset_id: str, cfg: Dash0Config, send: HttpSend = urllib_send
) -> Any:
    """GET the asset by ID. Raises RuntimeError with a redacted message on failure."""
    quoted = quote(asset_id, safe="")
    path = (
        f"/api/dashboards/{quoted}"
        if kind == "dashboard"
        else (f"/api/alerting/check-rules/{quoted}")
    )
    request = HttpRequest(
        method="GET",
        url=_url(cfg, path),
        headers=_headers(cfg, with_body=False),
        timeout=REQUEST_TIMEOUT_S,
    )
    try:
        response = send(request)
    except HttpTransportError as err:
        raise RuntimeError(_clip(f"read-back of {kind} failed: {err}", cfg.token)) from None
    text = _decode(response.body)
    if not response.ok:
        raise RuntimeError(
            _clip(f"read-back of {kind} failed: HTTP {response.status}: {text}", cfg.token)
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(
            _clip(f"read-back of {kind} returned non-JSON: {text}", cfg.token)
        ) from None
