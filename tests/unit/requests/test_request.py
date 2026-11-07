"""Unit tests: one Datadog request (queries + formulas) -> PromQL queries or a blocking diagnostic.

This is the main transformation unit. Cases come from
fixtures/expected/<service>/<dashboard>/expected.yaml (`requests:`), with the
input resolved from the pinned source dashboard by `source_path`.

Interface under test:
    migrator.source.datadog.load_mapping(path) -> Mapping
    migrator.source.datadog.translate_request(
        request: dict, *, mapping, variables: list[dict], source_path: str
    ) -> RequestResult
    RequestResult: dataclass with outcome ("translated" | "blocked"),
                   queries: list[str]  (PromQL, one per displayed formula, in order),
                   diagnostics: list[Diagnostic]
    Diagnostic: dataclass with code, severity, source_id, source_path, message,
                suggested_action, source_text
"""

from __future__ import annotations

import pytest

from support import as_plain, assert_diagnostics, canonical_list, case_params


def _translate(case):
    from migrator.source.datadog import load_mapping, translate_request

    return as_plain(
        translate_request(
            case.source_item,
            mapping=load_mapping(case.mapping_path),
            variables=case.variables,
            source_path=case.source_path,
        )
    )


@pytest.mark.parametrize("case", case_params("request"))
def test_request_translation(case):
    result = _translate(case)
    expected = case.expected
    assert result["outcome"] == expected["outcome"]
    if expected["outcome"] == "translated":
        # Compared after PromQL normalization (whitespace, parens, matcher order, + and * operand order).
        assert canonical_list(result["queries"]) == canonical_list(expected["promql"])
    else:
        assert result["queries"] == [], "a blocked request must not emit any series"
    assert_diagnostics(result, expected)


@pytest.mark.parametrize("case", case_params("request"))
def test_request_diagnostics_point_into_source(case):
    """Every diagnostic carries a source path inside the request it came from."""
    result = _translate(case)
    for d in result["diagnostics"]:
        assert d["source_path"].startswith(case.source_path), d
        assert d["message"], d
