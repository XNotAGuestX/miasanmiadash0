"""Golden: Postgres dashboards at the P1 level (plan 05 Task 9, standing in for plan 04 Task 4).

Regenerate by hand with `uv run migrator convert` and review the diff before committing.
Plan 05 Task 1 (documented default aggregator) is not implemented, so queries without a
space aggregator stay blocked with MISSING_AGGREGATOR, as the plan's fallback says.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from migrator.convert import ConvertOptions, run_convert

EXPECTED = Path("fixtures/expected/postgres-p1")
METRICS = "dashboards/postgresql_dashboard.json"
OVERVIEW = "dashboards/postgresql_screenboard_dashboard.json"


def tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.relative_to(root).as_posix().startswith("source/")
    }


def convert(out: Path) -> int:
    return run_convert(
        ConvertOptions(
            source="datadog",
            inputs=["fixtures/datadog/integrations-core/postgres/dashboards"],
            # Frozen copy, so edits to mappings/datadog/postgres.json do not churn the golden.
            mapping="fixtures/mappings/postgres.json",
            out=str(out),
            format="json",
            project="datadog-migration",
        )
    ).exit_code


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> tuple[int, Path]:
    out = tmp_path_factory.mktemp("pg") / "out"
    return convert(out), out


def report(out: Path) -> dict[str, Any]:
    data = json.loads((out / "report.json").read_text())
    assert isinstance(data, dict)
    return data


def widget_errors(rep: dict[str, Any], source_id: str, path: str) -> list[str]:
    return [
        d["code"]
        for d in rep["diagnostics"]
        if d["sourceId"] == source_id
        and d["severity"] == "error"
        and (d["sourcePath"] == path or d["sourcePath"].startswith(path + "."))
    ]


def test_postgres_p1_golden_matches_expected(run: tuple[int, Path]) -> None:
    code, out = run
    assert code == 2
    expected, actual = tree(EXPECTED), tree(out)
    assert sorted(actual) == sorted(expected)
    for rel, data in expected.items():
        assert actual[rel] == data, rel


def test_conversion_is_deterministic(run: tuple[int, Path], tmp_path: Path) -> None:
    _, first = run
    convert(tmp_path / "again")
    assert tree(tmp_path / "again") == tree(first)


def test_metrics_widget_outcomes(run: tuple[int, Path]) -> None:
    rep = report(run[1])
    outcomes = {
        i["sourcePath"]: i["outcome"]
        for i in rep["items"]
        if i["sourceId"] == METRICS and i["kind"] == "widget"
    }
    translated = sorted(int(p[8:-1]) for p, o in outcomes.items() if o == "translated")
    assert translated == [0, 1, 6, 8]
    expected_errors = {
        2: ["MISSING_AGGREGATOR"] * 3,  # Task 1 skipped: no documented default
        3: ["MISSING_METRIC_MAPPING"],  # system.io.util
        4: ["MISSING_AGGREGATOR"] * 3,
        5: ["MISSING_AGGREGATOR"] * 6,
        7: ["MISSING_METRIC_MAPPING"] * 2,  # system.mem.usable and system.mem.total
    }
    for n, codes in expected_errors.items():
        assert outcomes[f"widgets[{n}]"] == "blocked"
        assert widget_errors(rep, METRICS, f"widgets[{n}]") == codes, n


def test_connections_query_dedups_per_instance(run: tuple[int, Path]) -> None:
    d = json.loads((run[1] / "dashboards/postgres-metrics.json").read_text())
    query = d["spec"]["panels"]["widget-1"]["spec"]["queries"][0]["spec"]["plugin"]["spec"]
    assert query["query"] == (
        "avg by (postgresql_database_name) (max by (postgresql_database_name, "
        'service_instance_id) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"}))'
    )


def test_overview_is_partial_with_reviewed_counts(run: tuple[int, Path]) -> None:
    rep = report(run[1])
    items = [i for i in rep["items"] if i["sourceId"] == OVERVIEW]
    (dashboard,) = [i for i in items if i["kind"] == "dashboard"]
    assert dashboard["outcome"] == "partial"
    counts = Counter(i["outcome"] for i in items if i["kind"] == "widget")
    assert counts == {"translated": 8, "blocked": 22}
    assert (run[1] / "dashboards/postgres-overview.json").exists()
