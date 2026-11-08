"""Golden: the Docker dashboard at the P1 level (issue #115).

Regenerate by hand with `uv run migrator convert` (arguments as in `convert` below) and review
the diff before committing. The frozen copy fixtures/mappings/docker.json keeps edits to
mappings/datadog/docker.json from churning the golden.

No docker query reaches the mapping today: toplist, heatmap, event and image widgets block on
their type, timeseries and query_value widgets on their `time` (live_span) option. Only the
notes translate. Request-level PromQL is checked by the oracle suite (tests/unit/requests,
docker cases with --include-unreviewed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from migrator.convert import ConvertOptions, run_convert
from tests.test_golden_dashboards import tree

EXPECTED = Path("fixtures/expected/docker-p1")
DASHBOARD = "dashboards/docker_dashboard.json"
NOTES = [13, 16, 17, 19, 22]
TYPE_BLOCKED = [1, 2, 3, 6, 9, 10, 15, 25, 26, 27]  # toplist, heatmap, event_*, image


def convert(out: Path) -> int:
    return run_convert(
        ConvertOptions(
            source="datadog",
            inputs=["fixtures/datadog/integrations-core/docker_daemon/dashboards"],
            mapping=["fixtures/mappings/docker.json"],
            out=str(out),
            format="json",
            project="datadog-migration",
        )
    ).exit_code


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> tuple[int, Path]:
    out = tmp_path_factory.mktemp("docker") / "out"
    return convert(out), out


def report(out: Path) -> dict[str, Any]:
    data = json.loads((out / "report.json").read_text())
    assert isinstance(data, dict)
    return data


def test_docker_p1_golden_matches_expected(run: tuple[int, Path]) -> None:
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


def test_query_widgets_block_before_the_mapping(run: tuple[int, Path]) -> None:
    rep = report(run[1])
    outcomes = {
        i["sourcePath"]: i["outcome"]
        for i in rep["items"]
        if i["sourceId"] == DASHBOARD and i["kind"] == "widget"
    }
    translated = sorted(int(p[8:-1]) for p, o in outcomes.items() if o == "translated")
    assert translated == NOTES
    errors = [
        (d["sourcePath"], d["code"])
        for d in rep["diagnostics"]
        if d["sourceId"] == DASHBOARD and d["severity"] == "error"
    ]
    # One error per blocked widget, none from the mapping (no MISSING_METRIC_MAPPING).
    assert sorted(errors) == sorted(
        (f"widgets[{n}].definition.{'type' if n in TYPE_BLOCKED else 'time'}", "UNSUPPORTED_WIDGET")
        for n in range(len(outcomes))
        if n not in NOTES
    )
