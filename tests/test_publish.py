from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from migrator.cli import main
from migrator.convert import ConvertOptions, run_convert
from migrator.http import HttpRequest, HttpResponse, HttpTransportError
from migrator.input import InputError
from migrator.publish import PublishOptions, run_publish
from migrator.receipts import RECEIPTS_FILE, load_receipts

TOKEN = "dash0_TOKEN_secret"
ENV = {
    "DASH0_API_URL": "https://api.example.dash0.com",
    "DASH0_AUTH_TOKEN": TOKEN,
    "DASH0_DATASET": "default",
}
CHECK = "check-rules/postgres-number-of-connections-is-approaching-connection-limit-o.json"
DASH_METRICS = "dashboards/postgres-metrics.json"
DASH_OVERVIEW = "dashboards/postgres-overview.json"


class FakeSend:
    """Answers POSTs in order from `responses`; records every request."""

    def __init__(self, *responses: HttpResponse | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        res = self.responses.pop(0)
        if isinstance(res, Exception):
            raise res
        return res


def dashboard_ok(i: str) -> HttpResponse:
    return HttpResponse(200, json.dumps({"metadata": {"dash0Extensions": {"id": i}}}).encode())


def rule_ok(i: str) -> HttpResponse:
    return HttpResponse(200, json.dumps({"id": i}).encode())


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    out = tmp_path / "run"
    run_convert(
        ConvertOptions(
            source="datadog",
            inputs=["fixtures/datadog/integrations-core/postgres"],
            mapping="mappings/datadog/postgres.json",
            out=str(out),
        )
    )
    return out


def edit_manifest(run_dir: Path, entry_path: str, **changes: object) -> None:
    m = json.loads((run_dir / "manifest.json").read_text())
    for e in m["entries"]:
        if e["path"] == entry_path:
            e.update(changes)
    (run_dir / "manifest.json").write_text(json.dumps(m))


def test_dry_run_makes_no_requests(run_dir: Path) -> None:
    send = FakeSend()
    r = run_publish(PublishOptions(str(run_dir), dry_run=True, allow_partial=True), ENV, send)
    assert send.requests == []
    dry = [line for line in r.lines if line.startswith("DRY-RUN POST ")]
    assert len(dry) == 3
    assert dry[0].startswith(
        "DRY-RUN POST https://api.example.dash0.com/api/import/check-rule?dataset=default  "
        "[Postgres] Number of connections"
    )
    assert all(line.endswith("(publish)") for line in dry)
    assert not (run_dir / RECEIPTS_FILE).exists()


def test_rejects_paths_outside_the_run_dir(run_dir: Path) -> None:
    (run_dir.parent / "x.json").write_text("{}")
    edit_manifest(run_dir, CHECK, path="../x.json")
    send = FakeSend()
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert r.exit_code == 1
    assert send.requests == []
    assert "escapes the run directory" in r.lines[0]


def test_rejects_hash_mismatch(run_dir: Path) -> None:
    target = run_dir / CHECK
    target.write_text(target.read_text().replace('"1m"', '"2m"', 1))
    send = FakeSend()
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert (r.exit_code, send.requests) == (1, [])
    assert "sha256 mismatch" in r.lines[0]


def test_rejects_invalid_body_even_with_matching_hash(run_dir: Path) -> None:
    target = run_dir / CHECK
    body = json.loads(target.read_text())
    body["id"] = "existing"  # would overwrite in Dash0
    text = json.dumps(body)
    target.write_text(text)
    edit_manifest(run_dir, CHECK, sha256=hashlib.sha256(text.encode()).hexdigest())
    send = FakeSend()
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert (r.exit_code, send.requests) == (1, [])
    assert "failed validation" in r.lines[0]


def test_stops_on_auth_failure(run_dir: Path) -> None:
    send = FakeSend(HttpResponse(401, f"bad token {TOKEN}".encode()))
    r = run_publish(PublishOptions(str(run_dir), allow_partial=True), ENV, send)
    assert len(send.requests) == 1
    assert r.exit_code == 1
    assert any(line.startswith("stopping: HTTP 401") for line in r.lines)
    assert all(TOKEN not in line for line in r.lines)


def test_partial_requires_allow_partial(run_dir: Path) -> None:
    send = FakeSend(rule_ok("r1"))
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert r.exit_code == 2
    assert [req.url.split("?")[0].rsplit("/", 1)[1] for req in send.requests] == ["check-rule"]
    assert f"SKIP {DASH_METRICS}  (partial; pass --allow-partial to publish)" in r.lines

    send = FakeSend(dashboard_ok("d1"), dashboard_ok("d2"))
    r = run_publish(PublishOptions(str(run_dir), allow_partial=True), ENV, send)
    # check rule unchanged from the first run; both dashboards published now
    assert len(send.requests) == 2
    assert any(line.startswith(f"UNCHANGED {CHECK}") for line in r.lines)
    assert r.exit_code == 2  # replication_delay was still blocked in convert


def test_writes_receipts_per_asset(run_dir: Path) -> None:
    send = FakeSend(rule_ok("r1"), HttpResponse(400, b"bad dashboard"), dashboard_ok("d2"))
    r = run_publish(PublishOptions(str(run_dir), allow_partial=True), ENV, send)
    assert r.exit_code == 1
    saved = {x.path: x for x in load_receipts(run_dir)}
    assert (saved[CHECK].status, saved[CHECK].id) == ("imported", "r1")
    assert (saved[DASH_METRICS].status, saved[DASH_METRICS].http_status) == ("failed", 400)
    assert saved[DASH_OVERVIEW].status == "imported"
    assert r.receipts == sorted(saved.values(), key=lambda x: x.key)


def test_unknown_result_blocks_republish(run_dir: Path) -> None:
    send = FakeSend(HttpTransportError("TimeoutError: timed out"))
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert r.exit_code == 1
    assert load_receipts(run_dir)[0].status == "unknown"

    send = FakeSend()
    r = run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert (r.exit_code, send.requests) == (1, [])
    assert any(line.startswith(f"REFUSED {CHECK}") for line in r.lines)


def test_failed_asset_is_retried_on_next_run(run_dir: Path) -> None:
    run_publish(PublishOptions(str(run_dir)), ENV, FakeSend(HttpResponse(500, b"oops")))
    send = FakeSend(rule_ok("r1"))
    run_publish(PublishOptions(str(run_dir)), ENV, send)
    assert len(send.requests) == 1
    assert load_receipts(run_dir)[0].status == "imported"


def test_prometheus_rules_and_sources_are_never_sent(run_dir: Path) -> None:
    send = FakeSend(rule_ok("r1"), dashboard_ok("d1"), dashboard_ok("d2"))
    run_publish(PublishOptions(str(run_dir), allow_partial=True), ENV, send)
    kinds = [req.url.split("?")[0].rsplit("/", 1)[1] for req in send.requests]
    assert kinds == ["check-rule", "dashboard", "dashboard"]


def test_missing_env_names_variables_only(run_dir: Path) -> None:
    with pytest.raises(InputError, match="^missing env: DASH0_AUTH_TOKEN$"):
        run_publish(PublishOptions(str(run_dir)), {**ENV, "DASH0_AUTH_TOKEN": ""}, FakeSend())


def test_cli_dry_run(
    run_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    code = main(["publish", "--from", str(run_dir), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 2
    assert "DRY-RUN POST" in out and TOKEN not in out
