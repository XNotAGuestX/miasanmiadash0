"""Unit tests: one Datadog widget -> one Perses panel (or a blocked outcome).

A widget is all or nothing: never drop a series (00-context.md §8).

Interface under test:
    migrator.source.datadog.translate_widget(
        widget: dict, *, mapping, variables: list[dict], source_path: str
    ) -> WidgetResult
    WidgetResult: dataclass with outcome ("translated" | "blocked"),
                  panel_key: str | None  ("widget-<i>", group child "widget-<i>-<j>"),
                  panel: dict | None     (Perses Panel object),
                  diagnostics: list[Diagnostic]
"""

from __future__ import annotations

import pytest

from support import as_plain, assert_diagnostics, canonical_list, case_params


def _translate(case):
    from migrator.source.datadog import load_mapping, translate_widget

    return as_plain(
        translate_widget(
            case.source_item,
            mapping=load_mapping(case.mapping_path),
            variables=case.variables,
            source_path=case.source_path,
        )
    )


def _panel_queries(panel: dict) -> list[str]:
    return [q["spec"]["plugin"]["spec"]["query"] for q in panel["spec"]["queries"]]


@pytest.mark.parametrize("case", case_params("widget"))
def test_widget_translation(case):
    result = _translate(case)
    expected = case.expected
    assert result["outcome"] == expected["outcome"]
    assert_diagnostics(result, expected)
    if expected["outcome"] == "blocked":
        assert result["panel"] is None
        return
    panel = result["panel"]
    assert result["panel_key"] == expected["panel_key"]
    assert panel["kind"] == "Panel"
    assert panel["spec"]["display"]["name"] == expected["title"]
    assert panel["spec"]["plugin"]["kind"] == expected["panel_plugin"]
    assert {q["kind"] for q in panel["spec"]["queries"]} <= {"TimeSeriesQuery"}
    assert canonical_list(_panel_queries(panel)) == canonical_list(expected["promql"])
