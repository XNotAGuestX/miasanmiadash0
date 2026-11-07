"""Pinned fixtures for plan 08 Tasks 2-3. The goldens come later."""

from __future__ import annotations

from migrator.input import collect_input_files
from migrator.source.datadog.assets import recognize_assets

ROOT = "fixtures/datadog/integrations-core"


def test_recognizes_redis_dashboard_and_monitor() -> None:
    assets, diagnostics = recognize_assets(collect_input_files([f"{ROOT}/redisdb"]))
    assert diagnostics == []
    assert [a.kind for a in assets] == ["dashboard", "monitor"]
    assert assets[0].title == "Redis - Overview"
    assert assets[1].body["query"] == (
        "avg(last_5m):100 * avg:redis.mem.used{*} / avg:redis.mem.maxmemory{*} > 90"
    )


def test_recognizes_nginx_dashboard_and_seven_monitors() -> None:
    assets, diagnostics = recognize_assets(collect_input_files([f"{ROOT}/nginx"]))
    assert diagnostics == []
    assert [a.kind for a in assets] == ["dashboard"] + ["monitor"] * 7
    assert assets[0].title == "NGINX - Metrics"
