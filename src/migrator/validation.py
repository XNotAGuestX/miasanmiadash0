"""Validation of emitted artifacts: strict Perses schema and PromQL syntax.

These checks prove syntax and schema only, never API acceptance or semantics.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import promql_parser
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Grafana/Perses-style placeholders, substituted for the syntax check only.
_PLACEHOLDERS = {
    "$__rate_interval": "5m",
    "$__interval": "5m",
    "$__range": "5m",
    "$__threshold": "0",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Display(_Strict):
    name: str
    description: str


class _PromSpec(_Strict):
    query: Annotated[str, Field(min_length=1)]
    seriesNameFormat: str | None = None


class _PromPlugin(_Strict):
    kind: Literal["PrometheusTimeSeriesQuery"]
    spec: _PromSpec


class _QuerySpec(_Strict):
    plugin: _PromPlugin


class _Query(_Strict):
    kind: Literal["TimeSeriesQuery"]
    spec: _QuerySpec


class _PanelPlugin(_Strict):
    kind: Literal["TimeSeriesChart", "Markdown", "StatChart"]
    spec: dict[str, Any]


class _PanelSpec(_Strict):
    display: _Display
    plugin: _PanelPlugin
    queries: list[_Query]


class _Panel(_Strict):
    kind: Literal["Panel"]
    spec: _PanelSpec


class _Ref(_Strict):
    ref: str = Field(alias="$ref", pattern=r"^#/spec/panels/[A-Za-z0-9_-]+$")


class _GridItem(_Strict):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    width: Annotated[int, Field(gt=0, le=24)]
    height: Annotated[int, Field(gt=0)]
    content: _Ref


class _GridDisplay(_Strict):
    title: str


class _GridSpec(_Strict):
    display: _GridDisplay | None = None
    items: list[_GridItem]


class _Grid(_Strict):
    kind: Literal["Grid"]
    spec: _GridSpec


class _VarDisplay(_Strict):
    name: str


class _VarPluginSpec(_Strict):
    labelName: str


class _VarPlugin(_Strict):
    kind: Literal["PrometheusLabelValuesVariable"]
    spec: _VarPluginSpec


class _ListVariableSpec(_Strict):
    name: str
    display: _VarDisplay
    allowAllValue: bool
    allowMultiple: bool
    defaultValue: str
    plugin: _VarPlugin


class _ListVariable(_Strict):
    kind: Literal["ListVariable"]
    spec: _ListVariableSpec


class _Metadata(_Strict):
    name: Annotated[str, Field(pattern=r"^[a-z0-9-]+$")]
    project: Annotated[str, Field(min_length=1)]


class _DashboardSpec(_Strict):
    display: _Display
    duration: str
    variables: list[_ListVariable]
    panels: dict[str, _Panel]
    layouts: list[_Grid]


class _Dashboard(_Strict):
    kind: Literal["Dashboard"]
    metadata: _Metadata
    spec: _DashboardSpec


def validate_dashboard(d: Any) -> list[str]:
    """Return schema problems; an empty list means the dashboard matches the schema."""
    try:
        model = _Dashboard.model_validate(d)
    except ValidationError as err:
        return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()]
    problems: list[str] = []
    refs = [item.content.ref for grid in model.spec.layouts for item in grid.spec.items]
    keys = {f"#/spec/panels/{k}" for k in model.spec.panels}
    for ref in refs:
        if ref not in keys:
            problems.append(f"layouts: dangling reference {ref}")
    if len(refs) != len(set(refs)):
        problems.append("layouts: a panel is referenced more than once")
    for key in sorted(keys - set(refs)):
        problems.append(f"panels: {key} is not placed in any layout")
    return problems


def check_promql_syntax(expr: str) -> str | None:
    """Return None if ``expr`` parses as PromQL, else a short error message."""
    text = expr
    for placeholder, value in _PLACEHOLDERS.items():
        text = text.replace(placeholder, value)
    try:
        promql_parser.parse(text)
    except Exception as err:  # the parser raises ValueError subclasses
        return f"syntax error: {err}"
    return None
