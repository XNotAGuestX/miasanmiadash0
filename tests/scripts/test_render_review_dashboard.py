"""Offline tests for scripts/render_review_dashboard.py and scripts/review/load_local.py (issue #87).

Everything is written to tmp_path; committed fixtures are only read. No network: load_local talks to
an in-memory fake Perses through an injected opener.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest
import render_review_dashboard as rrd
from verify_common import load_case, load_expected

ROOT = Path(__file__).resolve().parents[2]
KEY = "postgres/postgresql_dashboard"
STAT_KEY = "redisdb/overview"  # has translated query_value requests
FIRST = "widgets[0].definition.requests[0]"


def _load_local() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("load_local", ROOT / "scripts" / "review" / "load_local.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ll = _load_local()


@pytest.fixture(autouse=True)
def _no_triage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: triage not importable (None in sys.modules makes `import triage` raise ImportError)."""
    monkeypatch.setitem(sys.modules, "triage", None)


def _fake_triage(monkeypatch: pytest.MonkeyPatch, rows: dict[str, dict[str, Any]]) -> list[str]:
    calls: list[str] = []
    mod = types.ModuleType("triage")

    def priorities(key: str) -> dict[str, dict[str, Any]]:
        calls.append(key)
        return rows

    mod.priorities = priorities  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "triage", mod)
    return calls


def _requests(key: str, outcome: str) -> list[dict[str, Any]]:
    """expected.yaml entries with this outcome, in case order."""
    entries = {e["source_path"]: e for e in load_expected(key)["requests"]}
    return [
        entries[r["source_path"]]
        for r in load_case(key)["requests"]
        if r["source_path"] in entries and entries[r["source_path"]]["expected"]["outcome"] == outcome
    ]


def _queries(panel: dict[str, Any]) -> list[str]:
    return [q["spec"]["plugin"]["spec"]["query"] for q in panel["spec"]["queries"]]


# --------------------------------------------------------------------------- render


@pytest.mark.parametrize("key", [KEY, STAT_KEY])
def test_one_panel_per_translated_request_with_exact_promql(key: str) -> None:
    d = rrd.render(key)
    translated = _requests(key, "translated")
    panels = d["spec"]["panels"]
    assert set(panels) == {f"req-{i}" for i in range(len(translated))} | {"blocked"}
    for i, entry in enumerate(translated):
        panel = panels[f"req-{i}"]
        assert _queries(panel) == entry["expected"]["promql"]
        assert panel["spec"]["display"]["name"].endswith(f"· {entry['source_path']}")
        assert all(q["kind"] == "TimeSeriesQuery" for q in panel["spec"]["queries"])
        assert all(q["spec"]["plugin"]["kind"] == "PrometheusTimeSeriesQuery" for q in panel["spec"]["queries"])


def test_query_value_requests_render_as_stat_chart() -> None:
    d = rrd.render(STAT_KEY)
    types_by_path = {r["source_path"]: r["widget_type"] for r in load_case(STAT_KEY)["requests"]}
    kinds = set()
    for i, entry in enumerate(_requests(STAT_KEY, "translated")):
        plugin = d["spec"]["panels"][f"req-{i}"]["spec"]["plugin"]
        want = "StatChart" if types_by_path[entry["source_path"]] == "query_value" else "TimeSeriesChart"
        assert plugin["kind"] == want
        kinds.add(want)
        if want == "StatChart":
            assert plugin["spec"] == {"calculation": "last-number"}
    assert kinds == {"StatChart", "TimeSeriesChart"}


def test_description_has_datadog_side_and_agent0_notes() -> None:
    desc = rrd.render(KEY)["spec"]["panels"]["req-0"]["spec"]["display"]["description"]
    assert "avg:postgresql.rows_fetched{$scope}" in desc
    assert "Formulas: `query1`" in desc
    # Note and triage text come from the recorded agent0 answer and verdicts, which are
    # regenerated, so compare against those files instead of a fixed sentence.
    assert f"agent0: {rrd.agent0_items(KEY)[FIRST]['notes']}" in desc
    assert re.search(r"^Triage: \S+; signals: ", desc, re.MULTILINE)


def test_blocked_requests_markdown_panel() -> None:
    d = rrd.render(KEY)
    blocked = _requests(KEY, "blocked")
    assert blocked  # this dashboard has blocked requests
    panel = d["spec"]["panels"]["blocked"]
    assert panel["spec"]["plugin"]["kind"] == "Markdown"
    assert panel["spec"]["queries"] == []
    text = panel["spec"]["plugin"]["spec"]["text"]
    assert f"Blocked requests ({len(blocked)})" in text
    case = load_case(KEY)
    for entry in blocked:
        assert entry["source_path"] in text
        for code in entry["expected"]["errors"]:
            assert f"`{code}`" in text
        req = next(r for r in case["requests"] if r["source_path"] == entry["source_path"])
        for q in req["queries"]:
            assert q["query"] in text
    # agent0's notes on the blocked requests (from the recorded answer)
    answers = rrd.agent0_items(KEY)
    noted = [answers[e["source_path"]]["notes"] for e in blocked if answers.get(e["source_path"], {}).get("notes")]
    assert noted
    for note in noted:
        assert f"agent0: {note}" in text
    # translated requests are not listed as blocked
    assert FIRST not in text


def test_layout_references_valid_panels_and_fits_the_grid() -> None:
    for key in (KEY, STAT_KEY):
        d = rrd.render(key)
        [grid] = d["spec"]["layouts"]
        assert grid["kind"] == "Grid"
        items = grid["spec"]["items"]
        refs = [i["content"]["$ref"] for i in items]
        assert sorted(refs) == sorted(f"#/spec/panels/{k}" for k in d["spec"]["panels"])  # each placed once
        for i in items:
            assert i["width"] > 0 and i["height"] > 0
            assert i["x"] >= 0 and i["y"] >= 0 and i["x"] + i["width"] <= 24
        # case order, two per row, markdown last and full width
        req_items = items[:-1]
        assert refs[:-1] == [f"#/spec/panels/req-{n}" for n in range(len(req_items))]
        assert [(i["x"], i["y"], i["width"], i["height"]) for i in req_items[:3]] == [
            (0, 0, 12, 8),
            (12, 0, 12, 8),
            (0, 8, 12, 8),
        ]
        last = items[-1]
        assert last["content"]["$ref"] == "#/spec/panels/blocked"
        assert (last["x"], last["width"]) == (0, 24)
        assert last["y"] >= max(i["y"] + i["height"] for i in req_items)


def test_metadata_name_slug_project_and_no_dash0_extensions() -> None:
    d = rrd.render("nginx/NGINX-Metrics_dashboard")
    assert d["metadata"] == {"name": "oracle-review-nginx-nginx-metrics-dashboard", "project": "oracle-review"}
    assert re.fullmatch(r"[a-z0-9-]+", d["metadata"]["name"])
    assert "dash0Extensions" not in json.dumps(d)
    assert d["spec"]["duration"] == "1h"
    assert "2026-11-07T14:05:00Z to 2026-11-07T15:21:00Z" in d["spec"]["display"]["description"]


def test_strict_publish_shape() -> None:
    """Same key sets as the strict schema `migrator publish` validates (PR #81 validation.py)."""
    d = rrd.render(STAT_KEY)
    assert set(d) == {"kind", "metadata", "spec"}
    assert set(d["spec"]) == {"display", "duration", "variables", "panels", "layouts"}
    assert set(d["spec"]["display"]) == {"name", "description"}
    for panel in d["spec"]["panels"].values():
        assert set(panel) == {"kind", "spec"} and panel["kind"] == "Panel"
        assert set(panel["spec"]) == {"display", "plugin", "queries"}
        assert set(panel["spec"]["display"]) == {"name", "description"}
        assert panel["spec"]["plugin"]["kind"] in {"TimeSeriesChart", "StatChart", "Markdown"}
        for q in panel["spec"]["queries"]:
            assert set(q["spec"]["plugin"]["spec"]) == {"query"} and q["spec"]["plugin"]["spec"]["query"]
    for item in d["spec"]["layouts"][0]["spec"]["items"]:
        assert set(item) == {"x", "y", "width", "height", "content"}


def test_title_truncates_widget_title_but_keeps_source_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rrd, "TITLE_MAX", 10)
    name = rrd.render(KEY)["spec"]["panels"]["req-0"]["spec"]["display"]["name"]
    assert name == f"[unverified] Rows fetc… · {FIRST}"


# --------------------------------------------------------------------------- triage


def test_triage_fallback_when_module_missing() -> None:
    assert rrd.load_priorities(KEY) == {}
    d = rrd.render(KEY)
    names = [p["spec"]["display"]["name"] for k, p in d["spec"]["panels"].items() if k != "blocked"]
    assert names and all(n.startswith("[unverified] ") for n in names)


def test_triage_fallback_when_function_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "triage", types.ModuleType("triage"))
    assert rrd.load_priorities(KEY) == {}


def test_priority_and_signals_from_triage(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked_sp = _requests(KEY, "blocked")[0]["source_path"]
    calls = _fake_triage(
        monkeypatch,
        {
            FIRST: {"priority": "red", "signals": {"lint": "pass", "judge": "block"}, "reasons": {"judge": ["wrong metric"]}},
            blocked_sp: {"priority": "yellow", "signals": {"judge": "nit"}},
        },
    )
    d = rrd.render(KEY)
    assert calls == [KEY]
    panels = d["spec"]["panels"]
    assert panels["req-0"]["spec"]["display"]["name"].startswith("[red] Rows fetched")
    assert panels["req-1"]["spec"]["display"]["name"].startswith("[unverified] ")  # not in triage output
    desc = panels["req-0"]["spec"]["display"]["description"]
    assert "Triage: red; signals: judge=block, lint=pass" in desc
    assert "- judge: wrong metric" in desc
    text = panels["blocked"]["spec"]["plugin"]["spec"]["text"]
    assert f"### [yellow] {blocked_sp}" in text
    assert "judge=nit" in text


# --------------------------------------------------------------------------- run dir


def test_write_run_manifest_matches_publish_format(tmp_path: Path) -> None:
    run = rrd.write_run(KEY, rrd.render(KEY), tmp_path)
    assert run == tmp_path / KEY
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["manifestVersion"] == 1 and manifest["format"] == "json"
    [entry] = manifest["entries"]
    assert entry["path"] == "dashboards/oracle-review-postgres-postgresql-dashboard.json"
    assert entry["kind"] == "dashboard"
    assert entry["outcome"] == "translated" and entry["eligible"] is True
    data = (run / entry["path"]).read_bytes()
    assert entry["sha256"] == hashlib.sha256(data).hexdigest()
    assert json.loads(data) == rrd.render(KEY)
    assert data.decode() == json.dumps(json.loads(data), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def test_output_is_deterministic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for out in ("a", "b"):
        assert rrd.main(["--all", "--out", str(tmp_path / out)]) == 0
    files_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*") if p.is_file())
    assert files_a == files_b and len(files_a) == 2 * len(rrd.all_keys())
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()
    text = "".join((tmp_path / "a" / rel).read_text() for rel in files_a)
    assert "2026-11-07T14:05:00Z" in text  # the fixed review window, nothing time-dependent
    assert str(tmp_path) not in text and str(ROOT) not in text


def test_cli_rejects_unknown_key_and_missing_args(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        rrd.main(["nope/missing", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        rrd.main(["--out", str(tmp_path)])
    assert not any(tmp_path.iterdir())


# --------------------------------------------------------------------------- load_local


class _Resp:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakePerses:
    """In-memory Perses REST API: GET/POST/PUT on /api/v1/... Drops empty fields on read like v0.55.1."""

    def __init__(self, existing: dict[str, Any] | None = None):
        self.store: dict[str, Any] = dict(existing or {})
        self.calls: list[tuple[str, str, Any]] = []

    def open(self, req: urllib.request.Request, timeout: float) -> _Resp:
        assert req.full_url.startswith("http://perses.test/")
        path = req.full_url.removeprefix("http://perses.test")
        body = json.loads(cast(bytes, req.data)) if req.data else None
        method = req.get_method()
        self.calls.append((method, path, body))
        if body is not None:
            assert req.get_header("Content-type") == "application/json"
        if method == "GET":
            if path not in self.store:
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b'{"message":"not found"}'))  # type: ignore[arg-type]
            stored = json.loads(json.dumps(self.store[path]))
            stored["metadata"]["version"] = 1
            return _Resp(200, json.dumps(ll.prune_empty(stored)).encode())
        if method == "POST":
            assert body is not None
            self.store[f"{path}/{body['metadata']['name']}"] = body
            return _Resp(200, json.dumps(body).encode())
        if method == "PUT":
            assert path in self.store
            self.store[path] = body
            return _Resp(200, json.dumps(body).encode())
        raise AssertionError(method)


def _run_dir(tmp_path: Path) -> Path:
    return Path(rrd.write_run(KEY, rrd.render(KEY), tmp_path / "out"))


DASH = "/api/v1/projects/oracle-review/dashboards"
NAME = "oracle-review-postgres-postgresql-dashboard"


def test_load_local_creates_everything_and_verifies(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = _run_dir(tmp_path)
    perses = FakePerses()
    env = {"DASH0_DATASET": "demo", "DASH0_API_URL": "https://api.example.dash0.com/", "DASH0_AUTH_TOKEN": "tok-SECRET"}
    assert ll.main([str(run), "--perses-url", "http://perses.test"], opener=perses, env=env) == 0
    writes = [(m, p) for m, p, _ in perses.calls if m != "GET"]
    assert writes == [
        ("POST", "/api/v1/projects"),
        ("POST", "/api/v1/projects/oracle-review/secrets"),
        ("POST", "/api/v1/projects/oracle-review/datasources"),
        ("POST", DASH),
    ]
    ds = perses.store["/api/v1/projects/oracle-review/datasources/dash0"]
    proxy = ds["spec"]["plugin"]["spec"]["proxy"]["spec"]
    assert proxy["url"] == "https://api.example.dash0.com/api/prometheus"
    assert proxy["headers"] == {"Dash0-Dataset": "demo"}
    assert proxy["secret"] == "dash0" and ds["spec"]["default"] is True
    secret = perses.store["/api/v1/projects/oracle-review/secrets/dash0"]
    assert secret["spec"]["authorization"] == {"type": "Bearer", "credentialsFile": "/run/secrets/dash0_auth_token"}
    sent = json.dumps([c[2] for c in perses.calls])
    assert "tok-SECRET" not in sent  # the token never leaves the environment
    dashboard = json.loads((run / "dashboards" / f"{NAME}.json").read_text())
    assert perses.store[f"{DASH}/{NAME}"] == dashboard
    out = capsys.readouterr().out
    assert "tok-SECRET" not in out
    assert f"created {NAME} (verified)" in out
    assert f"http://perses.test/projects/oracle-review/dashboards/{NAME}?start=1794060300000&end=1794064860000" in out


def test_load_local_puts_existing_dashboard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = _run_dir(tmp_path)
    existing = {
        "/api/v1/projects/oracle-review": ll.project_body(),
        "/api/v1/projects/oracle-review/secrets/dash0": ll.secret_body(),
        "/api/v1/projects/oracle-review/datasources/dash0": ll.datasource_body({}),
        f"{DASH}/{NAME}": {"kind": "Dashboard", "metadata": {"name": NAME, "project": "oracle-review"}, "spec": {}},
    }
    perses = FakePerses(existing)
    assert ll.main([str(run), "--perses-url", "http://perses.test"], opener=perses, env={}) == 0
    writes = [(m, p) for m, p, _ in perses.calls if m != "GET"]
    assert writes == [("PUT", f"{DASH}/{NAME}")]
    out = capsys.readouterr().out
    assert "project oracle-review: exists" in out and f"updated {NAME} (verified)" in out


def test_load_local_reports_changed_dashboard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    class Mangling(FakePerses):
        def open(self, req: urllib.request.Request, timeout: float) -> _Resp:
            resp = super().open(req, timeout)
            if req.get_method() == "GET" and "/dashboards/" in req.full_url:
                body = json.loads(resp.read())
                body["spec"]["duration"] = "6h"
                return _Resp(200, json.dumps(body).encode())
            return resp

    run = _run_dir(tmp_path)
    assert ll.main([str(run), "--perses-url", "http://perses.test"], opener=Mangling(), env={}) == 1
    assert "MISMATCH: spec differs" in capsys.readouterr().out


def test_load_local_rejects_sha_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = _run_dir(tmp_path)
    path = run / "dashboards" / f"{NAME}.json"
    path.write_text(path.read_text().replace('"1h"', '"2h"'))
    perses = FakePerses()
    assert ll.main([str(run), "--perses-url", "http://perses.test"], opener=perses, env={}) == 1
    assert "sha256 mismatch" in capsys.readouterr().err
    assert not any(p.startswith(DASH) for _, p, _ in perses.calls)


def test_load_local_loads_converter_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from migrator.cli import main as migrator_main

    run = tmp_path / "convert-out"
    args = [
        "convert", "--source", "datadog",
        "--input", str(ROOT / "fixtures/datadog/integrations-core/postgres"),
        "--mapping", str(ROOT / "mappings/datadog/postgres.json"),
        "--out", str(run),
    ]
    assert migrator_main(args) in (0, 2)
    capsys.readouterr()
    perses = FakePerses()
    assert ll.main([str(run), "--perses-url", "http://perses.test"], opener=perses, env={}) == 0
    writes = [(m, p) for m, p, _ in perses.calls if m != "GET"]
    dash = "/api/v1/projects/datadog-migration/dashboards"
    assert writes == [
        ("POST", "/api/v1/projects"),
        ("POST", "/api/v1/projects/datadog-migration/secrets"),
        ("POST", "/api/v1/projects/datadog-migration/datasources"),
        ("POST", dash),
        ("POST", dash),
    ]
    out = capsys.readouterr().out
    assert "created postgres-metrics (verified)" in out
    assert "http://perses.test/projects/datadog-migration/dashboards/postgres-overview?" in out


def test_datasource_defaults_without_env() -> None:
    proxy = ll.datasource_body({})["spec"]["plugin"]["spec"]["proxy"]["spec"]
    assert proxy["url"] == "https://api.eu-west-1.aws.dash0.com/api/prometheus"
    assert proxy["headers"] == {"Dash0-Dataset": "default"}


def test_prune_empty() -> None:
    assert ll.prune_empty({"a": [], "b": "", "c": {"d": {}}, "e": [{"f": ""}, 0], "g": False}) == {
        "e": [{}, 0],
        "g": False,
    }
