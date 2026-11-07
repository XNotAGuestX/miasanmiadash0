"""Offline tests for scripts/mutate_expected.py (known-bad expectation variants, issue #87)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lint_expected as le
import mutate_expected as me
import pytest
import verify_common as vc
import yaml

KEY = "postgres/postgresql_screenboard_dashboard"
SUM = 'rate({otel_metric_name="postgresql.tup_fetched", otel_metric_type="sum"}[$__rate_interval])'
REQ: dict[str, Any] = {"queries": [{"name": "query1", "query": "avg:postgresql.rows_fetched{*} by {db}"}], "formulas": ["query1"]}


def test_agg_swap() -> None:
    assert me.agg_swap([f"100 * max(avg by (h) ({SUM}))"], REQ) == [f"100 * min(avg by (h) ({SUM}))"]
    assert me.agg_swap([f"avg by (h) ({SUM})"], REQ) == [f"sum by (h) ({SUM})"]
    assert me.agg_swap([SUM], REQ) is None


def test_drop_by_label() -> None:
    assert me.drop_by_label([f"sum by (a, b) ({SUM})"], REQ) == [f"sum by (b) ({SUM})"]
    assert me.drop_by_label([f"sum by (a) ({SUM})"], REQ) == [f"sum ({SUM})"]
    assert me.drop_by_label([f"sum({SUM})"], REQ) is None


def test_rate_on_gauge_only_inside_rate() -> None:
    plain = '{otel_metric_name="postgresql.backends", otel_metric_type="sum"}'
    assert me.rate_on_gauge([f"sum({plain})"], REQ) is None
    got = me.rate_on_gauge([f"sum({plain})", f"sum({SUM})"], REQ)
    assert got is not None and got[0] == f"sum({plain})" and 'otel_metric_type="gauge"}[$__rate_interval]' in got[1]


def test_add_scale_skips_sources_with_100() -> None:
    assert me.add_scale([f"sum({SUM})"], REQ) == [f"100 * (sum({SUM}))"]
    ratio = {"queries": REQ["queries"], "formulas": ["query1 * 100"]}
    assert me.add_scale([f"sum({SUM}) * 100"], ratio) is None


def test_range_change() -> None:
    assert me.range_change([f"sum({SUM})"], REQ) == [f"sum({SUM.replace('$__rate_interval', '5m')})"]
    assert me.range_change(['sum({otel_metric_name="a"})'], REQ) is None


def test_sibling_metric_keeps_type_and_monotonicity() -> None:
    catalog = me.be.otel_catalog()
    other = me.sibling("postgresql.tup_fetched")
    assert other and other != "postgresql.tup_fetched" and other.startswith("postgresql.")
    assert (catalog[other]["type"], catalog[other]["monotonic"]) == ("sum", True)
    got = me.sibling_metric([f"sum({SUM}) / sum({SUM})"], REQ)
    assert got is not None and got[0].count(f'otel_metric_name="{other}"') == 2
    assert me.sibling("no.such.metric") is None


def test_only_translated_requests_are_mutated() -> None:
    assert me.mutate_entry(REQ, {"outcome": "blocked", "errors": ["MISSING_METRIC_MAPPING"]}) == []
    kinds = [m["mutation"] for m in me.mutate_entry(REQ, {"outcome": "translated", "promql": [f"avg by (x) ({SUM})"]})]
    assert kinds == list(me.STRUCTURAL)


def test_mutations_are_deterministic_and_parse() -> None:
    first, second = me.mutations_for(KEY), me.mutations_for(KEY)
    assert first == second
    assert len({m["id"] for m in first}) == len(first)
    for m in first:
        assert m["id"] == f"{m['source_path']}#{m['mutation']}"
        assert m["structural"] == me.STRUCTURAL[m["mutation"]]
        for q in m["expected"].get("promql") or []:
            assert le.parse_promql(q)[1] is None, q


@pytest.mark.parametrize("key", vc.all_keys())
def test_every_structural_mutation_is_caught_by_lint(key: str) -> None:
    case = vc.load_case(key)
    requests, answers = vc.case_requests(case), le.load_answers(key)
    missed = [
        m["id"]
        for m in me.mutations_for(key)
        if m["structural"]
        and le.verdict_of(le.lint_entry(requests[m["source_path"]], m["expected"], case, answers.get(m["source_path"]))) == "pass"
    ]
    assert missed == []


def test_each_structural_kind_occurs() -> None:
    kinds = {m["mutation"] for key in vc.all_keys() for m in me.mutations_for(key)}
    assert kinds == set(me.STRUCTURAL)


def test_write_and_lint_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc, "VERIFY_DIR", tmp_path)
    monkeypatch.setattr(vc, "MUTATIONS_DIR", tmp_path / "mutations")
    assert me.main([KEY]) == 0
    path = tmp_path / "mutations" / f"{KEY}.yaml"
    text = path.read_text()
    assert me.main([KEY]) == 0 and path.read_text() == text
    assert yaml.safe_load(text) == vc.load_mutations(KEY) == me.mutations_for(KEY)
    assert le.main([KEY, "--mutations"]) == 0
    verdicts = vc.read_verdicts(KEY, "lint", mutations=True)
    assert verdicts is not None and list(verdicts) == [m["id"] for m in vc.load_mutations(KEY)]
    flips = [v for k, v in verdicts.items() if k.endswith("#outcome_flip")]
    assert flips and all(v["verdict"] == "pass" for v in flips)  # semantic: invisible to the lint
