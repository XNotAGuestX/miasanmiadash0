"""Round trip (plan 10 Task 2): fetch by ID, then convert the fetched folder.

Compared against the P1 golden (#82), which stands in for the plan's P0 golden.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from migrator.cli import main
from migrator.convert import ConvertOptions, run_convert
from migrator.fetch import run_fetch
from migrator.http import HttpRequest, HttpResponse
from migrator.input import InputError
from migrator.source.asset import FetchSelection

PG = Path("fixtures/datadog/integrations-core/postgres")
DASHBOARD_ID = "abc-def-123"
MONITOR_ID = "4242"
ENV = {"DD_API_KEY": "ddapi_SECRET", "DD_APP_KEY": "ddapp_SECRET"}


def fake_datadog(req: HttpRequest) -> HttpResponse:
    if req.url.endswith(f"/api/v1/dashboard/{DASHBOARD_ID}"):
        return HttpResponse(200, (PG / "dashboards/postgresql_dashboard.json").read_bytes())
    if req.url.endswith(f"/api/v1/monitor/{MONITOR_ID}"):
        wrapped = json.loads((PG / "monitors/percent_usage_connections.json").read_text())
        # The API returns the inner definition, not integrations-core's wrapper.
        return HttpResponse(200, json.dumps(wrapped["definition"]).encode())
    return HttpResponse(404, b'{"errors": ["Not found"]}')


def test_fetched_folder_converts(tmp_path: Path) -> None:
    fetched = tmp_path / "fetched"
    written = run_fetch(
        "datadog", FetchSelection((DASHBOARD_ID,), (MONITOR_ID,)), str(fetched), ENV, fake_datadog
    )
    assert written == [f"dashboards/{DASHBOARD_ID}.json", f"monitors/{MONITOR_ID}.json"]

    out = tmp_path / "out"
    result = run_convert(
        ConvertOptions(
            source="datadog",
            inputs=[str(fetched)],
            mapping="mappings/datadog/postgres.json",
            out=str(out),
        )
    )
    expected = Path("fixtures/expected/postgres-p1/dashboards/postgres-metrics.json")
    assert (out / "dashboards/postgres-metrics.json").read_bytes() == expected.read_bytes()
    kinds = sorted(
        (i["kind"], i["sourceId"]) for i in result.report["items"] if i["sourcePath"] == ""
    )
    assert kinds == [
        ("dashboard", f"fetched/dashboards/{DASHBOARD_ID}.json"),
        ("monitor", f"fetched/monitors/{MONITOR_ID}.json"),
    ]


def test_cli_fetch_requires_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DD_API_KEY", raising=False)
    monkeypatch.delenv("DD_APP_KEY", raising=False)
    code = main(
        ["fetch", "--source", "datadog", "--dashboard-id", "a", "--out", str(tmp_path / "o")]
    )
    assert code == 1
    assert "missing env: DD_API_KEY, DD_APP_KEY" in capsys.readouterr().err


def test_cli_fetch_rejects_empty_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    code = main(["fetch", "--source", "datadog", "--out", str(tmp_path / "o")])
    assert code == 1
    assert "select at least one" in capsys.readouterr().err


def test_unknown_source_is_input_error(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="unknown --source"):
        run_fetch("nope", FetchSelection(("a",)), str(tmp_path / "o"), ENV, fake_datadog)
