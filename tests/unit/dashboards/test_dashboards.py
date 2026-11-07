"""Unit tests: a whole Datadog dashboard -> a Perses dashboard + per-widget outcomes.

Interface under test:
    migrator.source.datadog.translate_dashboard(
        dashboard: dict, *, mapping, project: str
    ) -> DashboardResult
    DashboardResult: dataclass with outcome ("translated" | "partial" | "blocked"),
                     dashboard: dict | None  (Perses Dashboard; None when blocked),
                     widgets: list[WidgetResult]  (one per leaf widget: every top-level
                         non-group widget and every group child, in source order;
                         plan 05 flattens groups into titled grids),
                     diagnostics: list[Diagnostic]
"""

from __future__ import annotations

import re

import pytest

from support import as_plain, canonical_json, canonical_list, case_params, leaf_widget_paths


def _translate(case):
    from migrator.source.datadog import load_mapping, translate_dashboard

    return as_plain(
        translate_dashboard(
            case.source_dashboard,
            mapping=load_mapping(case.mapping_path),
            project=case.spec["project"],
        )
    )


def _panel_queries(dashboard: dict) -> dict[str, list[str]]:
    return {
        key: canonical_list([q["spec"]["plugin"]["spec"]["query"] for q in panel["spec"].get("queries", [])])
        for key, panel in dashboard["spec"]["panels"].items()
    }


@pytest.mark.parametrize("case", case_params("dashboard"))
def test_dashboard_outcomes(case):
    result = _translate(case)
    expected = case.expected
    assert result["outcome"] == expected["outcome"]
    assert [w["source_path"] for w in result["widgets"]] == [w["source_path"] for w in expected["widgets"]]
    assert [w["outcome"] for w in result["widgets"]] == [w["outcome"] for w in expected["widgets"]]
    if expected["outcome"] == "blocked":
        assert result["dashboard"] is None, "a fully blocked dashboard writes no artifact"


@pytest.mark.parametrize("case", case_params("dashboard"))
def test_dashboard_panel_queries(case):
    """Exactly the translated widgets become panels, each with its expected PromQL."""
    result = _translate(case)
    expected = case.expected
    if expected["outcome"] == "blocked":
        pytest.skip("blocked dashboard has no panels")
    want = {w["panel_key"]: canonical_list(w["promql"]) for w in expected["widgets"] if w["outcome"] == "translated"}
    assert _panel_queries(result["dashboard"]) == want


@pytest.mark.parametrize("case", case_params("dashboard"))
def test_dashboard_structure_invariants(case):
    """Shape rules from 00-context.md §7 and plans 04/05, independent of the exact queries."""
    result = _translate(case)
    assert len(result["widgets"]) == len(leaf_widget_paths(case.source_dashboard)), "one outcome per leaf widget"
    translated = [w for w in result["widgets"] if w["outcome"] == "translated"]
    if not translated:
        assert result["outcome"] == "blocked" and result["dashboard"] is None
        return
    assert result["outcome"] == ("translated" if len(translated) == len(result["widgets"]) else "partial")
    dash = result["dashboard"]
    assert dash["kind"] == "Dashboard"
    assert dash["metadata"]["project"] == case.spec["project"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", dash["metadata"]["name"])
    assert "dash0Extensions" not in dash["metadata"], "never emit an id that overwrites a Dash0 dashboard"
    panels = dash["spec"]["panels"]
    assert all(re.fullmatch(r"widget-\d+(-\d+)?", key) for key in panels)
    items = [item for layout in dash["spec"]["layouts"] for item in layout["spec"]["items"]]
    assert sorted(item["content"]["$ref"] for item in items) == sorted(f"#/spec/panels/{k}" for k in panels)
    for item in items:
        assert 0 <= item["x"] and item["x"] + item["width"] <= 24, item


@pytest.mark.parametrize("case", case_params("dashboard"))
def test_dashboard_translation_is_deterministic(case):
    """Same input, mapping and version -> byte-identical output and diagnostics."""
    assert canonical_json(_translate(case)) == canonical_json(_translate(case))
