"""Tests for scripts/generate_vendor_mappings.py (#175)."""

from __future__ import annotations

from typing import Any

import generate_vendor_mappings as gen  # type: ignore[import-not-found]

from tests.datadog.test_metric_types import load_types, verdict

GAUGE = {"type": "gauge", "monotonic": None, "unit": "By", "sources": ["s.yaml"]}
COUNTER = {"type": "sum", "monotonic": True, "unit": "{op}", "sources": ["s.yaml"]}


def _dd(metric_type: str, per_unit: str = "") -> dict[str, str]:
    return {"metric_type": metric_type, "per_unit_name": per_unit, "unit_name": "", "source": "x"}


def _build(rows: list[dict[str, Any]], catalog: dict[str, Any], types: dict[str, Any]) -> Any:
    return gen.build(rows, catalog, types, set(), "2026-11-08")


def test_committed_file_is_current() -> None:
    text, _ = gen.generate()
    assert gen.OUT.read_text(encoding="utf-8") == text


def test_generated_kinds_follow_the_datadog_type_rule() -> None:
    types = load_types()
    metrics = gen.json.loads(gen.OUT.read_text(encoding="utf-8"))["metrics"]
    assert metrics
    assert {n: verdict(e["kind"], types.get(n)) for n, e in metrics.items()} == {
        n: "ok" for n in metrics
    }


def test_rate_from_monotonic_sum_with_filter_and_scale() -> None:
    rows = [{"datadog": "a.ops", "otel": "o.ops", "filter": {"op.type": "r"}, "transform": "× 100"}]
    body, skipped = _build(rows, {"o.ops": COUNTER}, {"a.ops": _dd("rate")})
    e = body["metrics"]["a.ops"]
    assert (e["kind"], e["target"], e["matchers"], e["scale"]) == (
        "rate",
        {"name": "o.ops", "type": "sum"},
        {"op_type": "r"},
        100,
    )
    assert skipped == {}


def test_inconsistent_or_ambiguous_rows_are_skipped() -> None:
    rows = [
        {"datadog": "a.gauge_of_counter", "otel": "o.ops"},
        {"datadog": "a.two", "otel": "o.ops"},
        {"datadog": "a.two", "otel": "o.bytes"},
        {"datadog": "a.unknown", "otel": "o.missing"},
    ]
    types = {n: _dd("gauge") for n in ("a.gauge_of_counter", "a.two", "a.unknown")}
    body, skipped = _build(rows, {"o.ops": COUNTER, "o.bytes": GAUGE}, types)
    assert body["metrics"] == {}
    assert skipped == {
        "a.gauge_of_counter": "Datadog kind gauge vs OTel cumulative sum",
        "a.two": "2 distinct table targets",
        "a.unknown": "o.missing not in the OTel catalog",
    }
