"""Parsed Datadog metric query types (the bounded subset only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SpaceAggregator = Literal["avg", "sum", "min", "max"]
SPACE_AGGREGATORS: tuple[SpaceAggregator, ...] = ("avg", "sum", "min", "max")

ParseErrorCode = Literal["UNSUPPORTED_QUERY_SYNTAX", "UNSUPPORTED_QUERY_FUNCTION"]


@dataclass(frozen=True)
class TagFilter:
    key: str
    value: str
    kind: Literal["tag"] = "tag"


@dataclass(frozen=True)
class VariableFilter:
    name: str
    kind: Literal["variable"] = "variable"


Filter = TagFilter | VariableFilter


@dataclass(frozen=True)
class QueryFunction:
    name: str
    args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetricQuery:
    aggregator: SpaceAggregator | None
    metric: str
    filters: list[Filter] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    functions: list[QueryFunction] = field(default_factory=list)


@dataclass(frozen=True)
class ParseOk:
    query: MetricQuery
    ok: Literal[True] = True


@dataclass(frozen=True)
class ParseError:
    code: ParseErrorCode
    offset: int
    message: str
    ok: Literal[False] = False


ParseResult = ParseOk | ParseError


# --- Monitor query types (plan 06 Task 1; appended by Track B) ----------------

TimeAggregator = Literal["avg", "max", "min", "sum"]
Comparator = Literal[">", ">=", "<", "<="]
WindowUnit = Literal["m", "h", "d"]


@dataclass(frozen=True)
class MonitorWindow:
    amount: int
    unit: WindowUnit


@dataclass(frozen=True)
class MonitorQuery:
    time_aggregator: TimeAggregator
    window: MonitorWindow
    query: MetricQuery
    comparator: Comparator
    threshold: float


@dataclass(frozen=True)
class MonitorParseOk:
    monitor: MonitorQuery
    ok: Literal[True] = True


MonitorParseResult = MonitorParseOk | ParseError
