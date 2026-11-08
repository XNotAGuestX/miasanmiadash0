"""Tests for scripts/generate_vendor_mappings.py (#175)."""

from __future__ import annotations

from typing import Any

import generate_vendor_mappings as gen  # type: ignore[import-not-found]
import pytest

from migrator.source.datadog.compile_query import CompiledError, CompiledOk
from migrator.source.datadog.mapping import parse_mapping
from tests.datadog.test_compile_query import run
from tests.datadog.test_metric_types import load_types, verdict

GAUGE = {"type": "gauge", "monotonic": None, "unit": "By", "sources": ["s.yaml"]}
COUNTER = {"type": "sum", "monotonic": True, "unit": "s", "sources": ["s.yaml"]}


def _dd(metric_type: str, per_unit: str = "", unit: str = "byte") -> dict[str, str]:
    return {"metric_type": metric_type, "per_unit_name": per_unit, "unit_name": unit, "source": "x"}


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
    rows = [{"datadog": "a.ops", "otel": "o.ops", "filter": {"op.type": "r"}, "transform": "× 1000"}]
    body, skipped = _build(rows, {"o.ops": COUNTER}, {"a.ops": _dd("rate", unit="millisecond")})
    e = body["metrics"]["a.ops"]
    assert (e["kind"], e["target"], e["matchers"], e["scale"]) == (
        "rate",
        {"name": "o.ops", "type": "sum"},
        {"op_type": "r"},
        1000,
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


def test_pinned_cpu_mapping_preserves_datadog_nanocore_values() -> None:
    text, _ = gen.generate()
    parsed = parse_mapping(gen.json.loads(text))
    assert parsed.ok
    result = run("avg:kubernetes.cpu.usage.total{*}", parsed.mapping)
    assert isinstance(result, CompiledOk)
    assert result.promql == (
        '(avg ({otel_metric_name="k8s.pod.cpu.usage", otel_metric_type="gauge"})) * 1000000000'
    )
    assert parsed.mapping.metrics["kubernetes.cpu.usage.total"].reviewed is None


@pytest.mark.parametrize(
    ("unit", "target_unit", "transform", "expected"),
    [
        ("byte", "By", "", 1),
        ("nanocore", "{cpu}", "", 1e9),
        ("nanocore", "{cpu}", "× 1000000000", 1e9),
        ("millisecond", "s", "× 1000", 1000),
        ("second", "{ms}", "× 0.001", 0.001),
        ("mebibyte", "By", "× 9.5367431640625e-7", 1 / 1024**2),
        ("fraction", "%", "× 0.01", 0.01),
    ],
)
def test_explicit_unit_factors(unit: str, target_unit: str, transform: str, expected: float) -> None:
    body, skipped = _build(
        [{"datadog": "a.value", "otel": "o.value", "transform": transform}],
        {"o.value": {**GAUGE, "unit": target_unit}},
        {"a.value": _dd("gauge", unit=unit)},
    )
    assert skipped == {}
    assert body["metrics"]["a.value"]["scale"] == expected


@pytest.mark.parametrize(
    ("unit", "target_unit", "per_unit"),
    [
        ("", "By", ""),
        ("byte", "", ""),
        ("unknown", "By", ""),
        ("byte", "{cpu}", ""),
        ("byte", "1", ""),
        ("transaction", "{transactions}/s", ""),
        ("byte", "By", "hour"),
    ],
)
def test_unknown_or_incompatible_units_stay_blocked(
    unit: str, target_unit: str, per_unit: str,
) -> None:
    body, skipped = _build(
        [{"datadog": "a.value", "otel": "o.value"}],
        {"o.value": {**GAUGE, "unit": target_unit}},
        {"a.value": _dd("gauge", per_unit=per_unit, unit=unit)},
    )
    assert body["metrics"] == {}
    assert "a.value" in skipped
    parsed = parse_mapping(body)
    assert parsed.ok
    result = run("avg:a.value{*}", parsed.mapping)
    assert isinstance(result, CompiledError)
    assert result.diagnostics[-1].code == "MISSING_METRIC_MAPPING"


@pytest.mark.parametrize("transform", ["× 1", "× 0", "× -1", "× nan", "× inf"])
def test_table_transform_must_agree_with_units(transform: str) -> None:
    body, skipped = _build(
        [{"datadog": "a.cpu", "otel": "o.cpu", "transform": transform}],
        {"o.cpu": {**GAUGE, "unit": "{cpu}"}},
        {"a.cpu": _dd("gauge", unit="nanocore")},
    )
    assert body["metrics"] == {}
    assert "conflicts with unit scale" in skipped["a.cpu"]


def test_conflicting_catalog_definition_is_skipped_even_when_first_type_matches() -> None:
    body, skipped = _build(
        [{"datadog": "a.memory", "otel": "o.memory"}],
        {"o.memory": {**GAUGE, "conflicts": ["other.yaml: type sum"]}},
        {"a.memory": _dd("gauge")},
    )
    assert body["metrics"] == {}
    assert skipped == {"a.memory": "o.memory has conflicting OTel definitions: other.yaml: type sum"}


def test_all_pinned_catalog_conflicts_remain_blocked() -> None:
    text, skipped = gen.generate()
    parsed = parse_mapping(gen.json.loads(text))
    assert parsed.ok
    for name in (
        "kubernetes.ephemeral_storage.usage",
        "kubernetes.memory.rss",
        "kubernetes.node.filesystem.usage",
    ):
        assert "conflicting OTel definitions" in skipped[name]
        result = run(f"avg:{name}{{*}}", parsed.mapping)
        assert isinstance(result, CompiledError)
        assert result.diagnostics[-1].code == "MISSING_METRIC_MAPPING"
