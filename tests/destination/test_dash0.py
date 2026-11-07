from __future__ import annotations

import json
from typing import Any, cast

import pytest

from migrator.destination.dash0 import (
    Dash0Config,
    Failed,
    Imported,
    Unknown,
    publish_check_rule,
    publish_dashboard,
    read_back,
    read_dash0_config,
)
from migrator.http import HttpRequest, HttpResponse, HttpTransportError
from migrator.input import InputError
from migrator.target import Dash0CheckRule, PersesDashboard

TOKEN = "auth_secret_TOKEN_123"
CFG = Dash0Config(api_url="https://api.example.dash0.com", token=TOKEN, dataset="my data/set")

DASHBOARD = cast(PersesDashboard, {"kind": "Dashboard", "metadata": {"name": "d"}, "spec": {}})
RULE = cast(
    Dash0CheckRule,
    {"name": "r", "expression": "up == 0", "thresholds": {"failed": 1}, "interval": "1m"},
)


class FakeSend:
    def __init__(self, response: HttpResponse | Exception) -> None:
        self.response = response
        self.requests: list[HttpRequest] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def ok(body: Any, status: int = 200) -> FakeSend:
    return FakeSend(HttpResponse(status, json.dumps(body).encode()))


def raw(status: int, text: str) -> FakeSend:
    return FakeSend(HttpResponse(status, text.encode()))


# --- config -----------------------------------------------------------------


def test_config_reports_missing_names_only() -> None:
    with pytest.raises(InputError, match="^missing env: DASH0_AUTH_TOKEN, DASH0_DATASET$"):
        read_dash0_config({"DASH0_API_URL": "https://x", "DASH0_AUTH_TOKEN": " "})


def test_config_strips_trailing_slash() -> None:
    cfg = read_dash0_config(
        {"DASH0_API_URL": "https://x.dash0.com/", "DASH0_AUTH_TOKEN": "t", "DASH0_DATASET": "d"}
    )
    assert cfg == Dash0Config("https://x.dash0.com", "t", "d")


def test_config_rejects_non_http_url() -> None:
    with pytest.raises(InputError, match="http"):
        read_dash0_config(
            {"DASH0_API_URL": "ftp://x", "DASH0_AUTH_TOKEN": "t", "DASH0_DATASET": "d"}
        )


# --- publish ----------------------------------------------------------------


def test_dashboard_request_shape() -> None:
    send = ok({"metadata": {"dash0Extensions": {"id": "abc"}}})
    assert publish_dashboard(DASHBOARD, CFG, send) == Imported(id="abc", http_status=200)
    (req,) = send.requests
    assert req.method == "POST"
    assert req.url == "https://api.example.dash0.com/api/import/dashboard?dataset=my%20data%2Fset"
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert req.headers["Accept"] == "application/json"
    assert req.headers["Content-Type"] == "application/json"
    assert req.timeout == 30.0
    assert req.body is not None and json.loads(req.body) == DASHBOARD


def test_check_rule_request_and_id() -> None:
    send = ok({"id": "rule-1"}, status=201)
    assert publish_check_rule(RULE, CFG, send) == Imported(id="rule-1", http_status=201)
    assert send.requests[0].url.startswith(
        "https://api.example.dash0.com/api/import/check-rule?dataset="
    )


def test_refuses_dashboard_with_dash0_extensions_before_request() -> None:
    send = ok({})
    body = cast(PersesDashboard, {"metadata": {"name": "d", "dash0Extensions": {"id": "x"}}})
    with pytest.raises(InputError, match="create-only"):
        publish_dashboard(body, CFG, send)
    assert send.requests == []


def test_refuses_check_rule_with_id_before_request() -> None:
    send = ok({})
    body = cast(Dash0CheckRule, {**RULE, "id": "x"})
    with pytest.raises(InputError, match="create-only"):
        publish_check_rule(body, CFG, send)
    assert send.requests == []


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_are_unknown(status: int) -> None:
    # The asset may already exist, so a 5xx must never allow a blind republish.
    out = publish_dashboard(DASHBOARD, CFG, raw(status, "server error"))
    assert isinstance(out, Unknown)
    assert f"HTTP {status}" in out.message


def test_transport_error_is_unknown() -> None:
    out = publish_dashboard(DASHBOARD, CFG, FakeSend(HttpTransportError("TimeoutError: timed out")))
    assert isinstance(out, Unknown)
    assert "may or may not exist" in out.message


def test_other_non_2xx_is_failed_and_clipped() -> None:
    out = publish_dashboard(DASHBOARD, CFG, raw(400, "x" * 2000))
    assert isinstance(out, Failed)
    assert out.http_status == 400
    assert len(out.message) == 500


def test_unauthorized_is_failed_with_status_401() -> None:
    out = publish_dashboard(DASHBOARD, CFG, raw(401, "unauthorized"))
    assert isinstance(out, Failed)
    assert out.http_status == 401


def test_redirect_status_is_failed() -> None:
    out = publish_dashboard(DASHBOARD, CFG, raw(302, ""))
    assert isinstance(out, Failed)
    assert out.http_status == 302


def test_non_json_2xx_is_unknown() -> None:
    assert isinstance(publish_dashboard(DASHBOARD, CFG, raw(200, "<html>")), Unknown)


def test_2xx_without_id_is_unknown() -> None:
    out = publish_dashboard(DASHBOARD, CFG, ok({"metadata": {}}))
    assert isinstance(out, Unknown)
    assert "metadata.dash0Extensions.id" in out.message


def test_empty_id_is_unknown() -> None:
    assert isinstance(publish_check_rule(RULE, CFG, ok({"id": ""})), Unknown)


@pytest.mark.parametrize(
    "send",
    [
        raw(401, f"invalid token {TOKEN}"),
        raw(502, f"echo {TOKEN}"),
        raw(200, f"not json {TOKEN}"),
        FakeSend(HttpTransportError(f"reset while sending {TOKEN}")),
    ],
)
def test_token_never_leaks_into_outcome(send: FakeSend) -> None:
    out = publish_dashboard(DASHBOARD, CFG, send)
    assert not isinstance(out, Imported)
    assert TOKEN not in out.message
    assert "<redacted>" in out.message


# --- read-back --------------------------------------------------------------


def test_read_back_dashboard_url_and_body() -> None:
    send = ok({"kind": "Dashboard"})
    assert read_back("dashboard", "a/b", CFG, send) == {"kind": "Dashboard"}
    (req,) = send.requests
    assert req.method == "GET"
    assert req.url == "https://api.example.dash0.com/api/dashboards/a%2Fb?dataset=my%20data%2Fset"
    assert "Content-Type" not in req.headers


def test_read_back_check_rule_url() -> None:
    send = ok({"id": "r"})
    read_back("check-rule", "r", CFG, send)
    assert "/api/alerting/check-rules/r?" in send.requests[0].url


def test_read_back_failure_is_redacted() -> None:
    with pytest.raises(RuntimeError, match="HTTP 404") as info:
        read_back("dashboard", "x", CFG, raw(404, f"nope {TOKEN}"))
    assert TOKEN not in str(info.value)


def test_read_back_transport_error_raises() -> None:
    with pytest.raises(RuntimeError, match="read-back"):
        read_back("dashboard", "x", CFG, FakeSend(HttpTransportError("down")))
