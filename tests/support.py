"""Shared test helpers (imported by test modules): case loading, source-path resolution.

Expectations live in fixtures/expected/<service>/<dashboard_id>/expected.yaml.
Source inputs are resolved from the pinned dashboard by JSON source path, so the
request/widget input is never duplicated in the expectation file.
"""

from __future__ import annotations

import dataclasses
import json
import re

from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
SOURCE_DIR = FIXTURES / "datadog" / "integrations-core"
EXPECTED_DIR = FIXTURES / "expected"
SYNTHETIC_DIR = FIXTURES / "synthetic"

# --------------------------------------------------------------------------- loading

_TOKEN = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


def resolve(document: Any, source_path: str) -> Any:
    """Resolve 'widgets[1].definition.requests[0]' inside a parsed JSON document."""
    node = document
    pos = 0
    while pos < len(source_path):
        m = _TOKEN.match(source_path, pos)
        if not m:
            raise ValueError(f"bad source path {source_path!r} at {pos}")
        node = node[m.group(1)] if m.group(1) is not None else node[int(m.group(2))]
        pos = m.end()
    return node


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def source_dashboards() -> list[Path]:
    return sorted(SOURCE_DIR.glob("*/dashboards/*.json"))


def expected_files() -> list[Path]:
    return sorted(EXPECTED_DIR.glob("*/*/expected.yaml"))


@dataclasses.dataclass(frozen=True)
class Case:
    """One expectation entry plus everything needed to run it."""

    case_id: str
    level: str  # "request" | "widget" | "dashboard"
    source_path: str
    expected: dict
    milestone: str
    reviewed: bool
    spec: dict  # the whole expected.yaml (mapping, project, fixture, ...)
    spec_dir: Path

    @property
    def source_dashboard(self) -> dict:
        return load_json(ROOT / self.spec["source_fixture"])

    @property
    def source_item(self) -> Any:
        doc = self.source_dashboard
        return doc if self.source_path == "" else resolve(doc, self.source_path)

    @property
    def mapping_path(self) -> Path:
        return ROOT / self.spec["mapping"]

    @property
    def variables(self) -> list[dict]:
        return self.source_dashboard.get("template_variables", [])


def iter_cases(level: str) -> Iterator[Case]:
    key = {"request": "requests", "widget": "widgets"}.get(level)
    for path in expected_files():
        spec = yaml.safe_load(path.read_text())
        dash_id = f"{path.parent.parent.name}/{path.parent.name}"
        if level == "dashboard":
            entry = spec.get("dashboard")
            if entry:
                yield Case(dash_id, level, "", entry["expected"], entry["milestone"], bool(entry["reviewed"]), spec, path.parent)
            continue
        for entry in spec.get(key) or []:
            yield Case(
                f"{dash_id}/{entry['source_path']}",
                level,
                entry["source_path"],
                entry["expected"],
                entry["milestone"],
                bool(entry["reviewed"]),
                spec,
                path.parent,
            )


def case_params(level: str) -> list:
    params = []
    for case in iter_cases(level):
        marks = [getattr(pytest.mark, case.milestone)]
        if not case.reviewed:
            marks.append(pytest.mark.unreviewed)
        params.append(pytest.param(case, id=case.case_id, marks=marks))
    if not params:
        params.append(pytest.param(None, id=f"no-{level}-cases", marks=pytest.mark.skip(reason=f"no {level} expectations recorded yet")))
    return params


# --------------------------------------------------------------------------- result helpers


def as_plain(obj: Any) -> Any:
    """Convert dataclass results to plain dicts/lists so tests don't depend on classes."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: as_plain(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: as_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [as_plain(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(as_plain(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------- PromQL comparison

_GRAFANA_VARS = re.compile(r"\$__(rate_interval|interval|range)")


def canonical_promql(query: str) -> str:
    """Normalize PromQL so semantically identical renderings compare equal.

    Ignores whitespace, redundant parentheses, matcher order, label order in
    by/without, and operand order of `+` / `*` without vector-matching modifiers.
    Does NOT treat different metrics, functions, matchers or aggregations as equal.
    """
    import promql_parser

    expr = promql_parser.parse(_GRAFANA_VARS.sub("5m", query))
    return _canon(expr)


def _canon(node: Any) -> str:
    kind = type(node).__name__
    if kind == "ParenExpr":
        return _canon(node.expr)
    if kind == "BinaryExpr":
        lhs, rhs, op = _canon(node.lhs), _canon(node.rhs), str(node.op)
        mod = str(node.modifier) if node.modifier else ""
        if op in ("+", "*") and not mod:
            lhs, rhs = sorted([lhs, rhs])
        return f"({lhs} {op}{' ' + mod if mod else ''} {rhs})"
    if kind == "AggregateExpr":
        mod = ""
        if node.modifier is not None:
            word = "by" if "By" in str(node.modifier.type) else "without"
            mod = f" {word} ({', '.join(sorted(node.modifier.labels))})"
        param = f"{_canon(node.param)}, " if node.param is not None else ""
        return f"{node.op}{mod}({param}{_canon(node.expr)})"
    if kind == "Call":
        return f"{node.func.name}({', '.join(_canon(a) for a in node.args)})"
    if kind == "NumberLiteral":
        return repr(float(node.val))
    if kind == "UnaryExpr":
        return f"(-{_canon(node.expr)})"
    return node.prettify()  # selectors (matchers already sorted), strings, subqueries


def canonical_list(queries: list[str]) -> list[str]:
    return [canonical_promql(q) for q in queries]


# --------------------------------------------------------------------------- diagnostics


def codes(diagnostics: list, severity: str) -> list[str]:
    plain = as_plain(diagnostics)
    return sorted(d["code"] for d in plain if d["severity"] == severity)


def assert_diagnostics(result: dict, expected: dict) -> None:
    """Errors are always exact. Warnings are exact only for translated items."""
    assert codes(result["diagnostics"], "error") == sorted(expected.get("errors", []))
    if expected["outcome"] == "translated":
        assert codes(result["diagnostics"], "warning") == sorted(expected.get("warnings", []))


def leaf_widget_paths(dashboard: dict) -> list[str]:
    """Source paths of every top-level non-group widget and every group child, in order."""
    paths = []
    for i, widget in enumerate(dashboard.get("widgets", [])):
        definition = widget.get("definition", {})
        if definition.get("type") == "group":
            paths.extend(f"widgets[{i}].definition.widgets[{j}]" for j in range(len(definition.get("widgets", []))))
        else:
            paths.append(f"widgets[{i}]")
    return paths
