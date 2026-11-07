"""Datadog metric monitors (plan 06): query parser and options allowlist.

Deterministic and rule-based only. The inner metric query goes through the shared
dashboard parser; anything outside the bounded grammar blocks the monitor.
"""

from __future__ import annotations

import re
from typing import cast

from migrator.source.datadog.model import (
    Comparator,
    MonitorParseOk,
    MonitorParseResult,
    MonitorQuery,
    MonitorWindow,
    ParseError,
    ParseOk,
    TimeAggregator,
    WindowUnit,
)
from migrator.source.datadog.parse_query import parse_metric_query

_PREFIX = re.compile(r"^(avg|max|min|sum)\(last_(\d+)(m|h|d)\):")
_SUFFIX = re.compile(r" (>=|<=|>|<) (-?\d+(?:\.\d+)?)$")


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def parse_monitor_query(text: str) -> MonitorParseResult:
    prefix = _PREFIX.match(text)
    if prefix is None:
        return ParseError(
            code="UNSUPPORTED_QUERY_SYNTAX",
            offset=0,
            message="Expected '<avg|max|min|sum>(last_<n><m|h|d>):' at offset 0.",
        )
    suffix = _SUFFIX.search(text, prefix.end())
    if suffix is None:
        offset = _utf16_len(text)
        return ParseError(
            code="UNSUPPORTED_QUERY_SYNTAX",
            offset=offset,
            message=f"Expected ' <comparator> <number>' at the end of the query (offset {offset}).",
        )

    inner = parse_metric_query(text[prefix.end() : suffix.start()])
    if not isinstance(inner, ParseOk):
        shift = _utf16_len(text[: prefix.end()])
        # Function errors carry offset 0 (the whole query); syntax errors point at a char.
        return ParseError(code=inner.code, offset=inner.offset + shift, message=inner.message)

    return MonitorParseOk(
        monitor=MonitorQuery(
            time_aggregator=cast(TimeAggregator, prefix.group(1)),
            window=MonitorWindow(
                amount=int(prefix.group(2)), unit=cast(WindowUnit, prefix.group(3))
            ),
            query=inner.query,
            comparator=cast(Comparator, suffix.group(1)),
            threshold=float(suffix.group(2)),
        )
    )
