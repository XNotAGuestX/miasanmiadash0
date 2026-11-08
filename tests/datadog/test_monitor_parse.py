from __future__ import annotations

import json
from pathlib import Path

from migrator.source.datadog.model import (
    MetricQuery,
    MonitorParseOk,
    MonitorQuery,
    MonitorWindow,
    ParseError,
)
from migrator.source.datadog.monitor import ARITHMETIC, parse_monitor_query
from migrator.source.datadog.parse_query import parse_metric_query

PINNED = Path("fixtures/datadog/integrations-core/postgres/monitors")


def pinned_query(name: str) -> str:
    query = json.loads((PINNED / name).read_text())["definition"]["query"]
    assert isinstance(query, str)
    return query


def test_parses_the_golden_monitor() -> None:
    r = parse_monitor_query(pinned_query("percent_usage_connections.json"))
    assert r == MonitorParseOk(
        MonitorQuery(
            time_aggregator="avg",
            window=MonitorWindow(15, "m"),
            query=MetricQuery(aggregator="avg", metric="postgresql.percent_usage_connections"),
            comparator=">",
            threshold=0.9,
        )
    )


def test_blocks_anomalies() -> None:
    r = parse_monitor_query(pinned_query("replication_delay.json"))
    assert isinstance(r, ParseError)
    assert r.code == "UNSUPPORTED_QUERY_FUNCTION"
    assert r.message.startswith("Function 'anomalies' is not supported: ")
    assert "docs.datadoghq.com/monitors/types/anomaly/" in r.message


def test_blocks_arithmetic() -> None:
    r = parse_monitor_query(
        "avg(last_5m):100 * avg:redis.mem.used{*} / avg:redis.mem.maxmemory{*} > 90"
    )
    assert isinstance(r, ParseError)
    assert (r.code, r.offset, r.message) == ("UNSUPPORTED_QUERY_SYNTAX", 13, ARITHMETIC)
    for inner in ["avg:a{*} - avg:b{*}", "(avg:a{*}) + 1", "-avg:a{*}", "avg:a{*} * 2"]:
        r = parse_monitor_query(f"avg(last_5m):{inner} > 1")
        assert isinstance(r, ParseError) and r.message == ARITHMETIC, inner
    # Tag values with '-' or '/' are not arithmetic.
    r = parse_monitor_query("avg(last_5m):avg:a{env:prod-1,path:/x} by {host}junk > 1")
    assert isinstance(r, ParseError) and r.message != ARITHMETIC


def test_blocks_unknown_window_unit() -> None:
    r = parse_monitor_query("avg(last_1w):avg:x{*} > 1")
    assert isinstance(r, ParseError)
    assert (r.code, r.offset) == ("UNSUPPORTED_QUERY_SYNTAX", 0)


def test_parses_comparators_negative_and_hours() -> None:
    r = parse_monitor_query("max(last_2h):sum:x{a:b} by {host} <= -1.5")
    assert isinstance(r, MonitorParseOk)
    m = r.monitor
    assert (m.time_aggregator, m.window, m.comparator, m.threshold) == (
        "max",
        MonitorWindow(2, "h"),
        "<=",
        -1.5,
    )
    assert m.query.group_by == ["host"]


def test_blocks_missing_threshold_at_end() -> None:
    text = "avg(last_5m):avg:x{*}"
    r = parse_monitor_query(text)
    assert isinstance(r, ParseError)
    assert (r.code, r.offset) == ("UNSUPPORTED_QUERY_SYNTAX", len(text))


def test_inner_syntax_offsets_are_shifted_by_the_prefix() -> None:
    prefix = "avg(last_5m):"
    inner = "avg:x{*"
    direct = parse_monitor_query(f"{prefix}{inner} > 1")
    assert isinstance(direct, ParseError)
    alone = parse_metric_query(inner)
    assert isinstance(alone, ParseError)
    assert direct.offset == alone.offset + len(prefix)
