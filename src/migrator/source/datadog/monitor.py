"""Datadog metric monitors (plan 06): query parser and options allowlist.

Deterministic and rule-based only. The inner metric query goes through the shared
dashboard parser; anything outside the bounded grammar blocks the monitor.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

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
from migrator.target import Diagnostic, DiagnosticCode, Severity

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


# --- Options allowlist (plan 06 Task 2, decision A3) ---------------------------


@dataclass(frozen=True)
class MonitorThresholds:
    critical: float
    warning: float | None = None


@dataclass(frozen=True)
class OptionsOk:
    thresholds: MonitorThresholds
    diagnostics: list[Diagnostic] = field(default_factory=list)
    ok: Literal[True] = True


@dataclass(frozen=True)
class OptionsBlocked:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    ok: Literal[False] = False


OptionsResult = OptionsOk | OptionsBlocked


def _is_number(v: Any) -> bool:
    # bool is an int subclass in Python; Datadog JSON true/false must never pass as 1/0.
    return isinstance(v, int | float) and not isinstance(v, bool)


def _is_finite(v: Any) -> bool:
    return _is_number(v) and math.isfinite(v)


def _is_zero(v: Any) -> bool:
    return _is_number(v) and v == 0


# key -> accepted-silently predicate. Anything else for these keys blocks the monitor.
_STRICT_DEFAULTS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "notify_no_data": (lambda v: v is False, "false"),
    "no_data_timeframe": (lambda v: v is None, "null"),
    "timeout_h": (lambda v: v is None or _is_zero(v), "0 or null"),
    "renotify_interval": (lambda v: v is None or _is_zero(v) or v == "0", "0 or null"),
    "escalation_message": (lambda v: v == "", "an empty string"),
    "notify_audit": (lambda v: v is False, "false"),
    "locked": (lambda v: v is False, "false"),
}

_STRICT_REASONS: dict[str, str] = {
    "notify_no_data": "Dash0 handles missing data differently from Datadog no-data alerts.",
    "no_data_timeframe": "Dash0 has no no-data timeframe.",
    "timeout_h": "Dash0 has no auto-resolve timeout.",
    "renotify_interval": "Re-notification is configured in Dash0 notification channels.",
    "escalation_message": "Escalation messages are not migrated.",
    "notify_audit": "Audit notifications are not migrated.",
    "locked": "Monitor locking has no Dash0 equivalent.",
}


def evaluate_monitor_options(options: Mapping[str, Any], *, source_id: str) -> OptionsResult:
    """Check `options` against the reviewed allowlist. Unknown or semantically
    different options block the monitor; diagnostics are sorted by source path."""
    diags: list[Diagnostic] = []

    def add(code: DiagnosticCode, severity: Severity, path: str, message: str, action: str) -> None:
        diags.append(Diagnostic(code, severity, source_id, path, message, action))

    def block(path: str, message: str) -> None:
        add(
            "UNSUPPORTED_MONITOR_OPTION",
            "error",
            path,
            message,
            "Migrate this monitor manually or change the option to its default.",
        )

    critical: float | None = None
    warning: float | None = None

    for key in sorted(options):
        value = options[key]
        path = f"options.{key}"
        if key == "thresholds":
            if not isinstance(value, Mapping):
                block(path, "Monitor thresholds must be an object.")
                continue
            for tkey in sorted(value):
                tval = value[tkey]
                tpath = f"{path}.{tkey}"
                if tkey not in ("critical", "warning"):
                    block(tpath, f"Threshold '{tkey}' is not supported.")
                elif not _is_finite(tval):
                    block(tpath, f"Threshold '{tkey}' must be a finite number.")
                elif tkey == "critical":
                    critical = float(tval)
                else:
                    warning = float(tval)
            if "critical" not in value:
                block(path, "Monitor has no critical threshold.")
        elif key == "require_full_window":
            if value is True:
                add(
                    "MONITOR_OPTION_APPROXIMATED",
                    "warning",
                    path,
                    "Dash0 evaluates partial windows.",
                    "Check that early evaluations of a new series are acceptable.",
                )
            elif value is not False:
                block(path, "require_full_window must be true or false.")
        elif key == "new_host_delay":
            if _is_number(value) and value > 0:
                add(
                    "MONITOR_OPTION_APPROXIMATED",
                    "warning",
                    path,
                    "No new-host grace period in Dash0.",
                    "Expect alerts from new hosts right after they start reporting.",
                )
            elif not (value is None or _is_zero(value)):
                block(path, "new_host_delay must be null or a non-negative number.")
        elif key == "include_tags":
            if isinstance(value, bool):
                add(
                    "OPTION_IGNORED",
                    "info",
                    path,
                    "Monitor option 'include_tags' is ignored.",
                    "No action needed; notification titles are not migrated.",
                )
            else:
                block(path, "include_tags must be true or false.")
        elif key in _STRICT_DEFAULTS:
            accepts, expected = _STRICT_DEFAULTS[key]
            if not accepts(value):
                block(path, f"Only {expected} is supported for '{key}'. {_STRICT_REASONS[key]}")
        else:
            block(path, f"Monitor option '{key}' is not supported.")

    if "thresholds" not in options:
        block("options.thresholds", "Monitor has no thresholds.")

    diags.sort(key=lambda d: d.source_path)
    if critical is None or any(d.severity == "error" for d in diags):
        return OptionsBlocked(diagnostics=diags)
    return OptionsOk(thresholds=MonitorThresholds(critical, warning), diagnostics=diags)
