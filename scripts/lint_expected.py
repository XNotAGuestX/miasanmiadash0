"""L0 deterministic lint of the agent0-derived expectations (development time only, issue #87).

Reads fixtures/expected/<key>/expected.yaml, the case inventory and the frozen agent0 answer, and grades
every request entry pass | nit | block with short reasons. No LLM, no network, no timestamps: the same
inputs always give the same verdict file. Verdicts are triage signals for the human reviewer, never
approval (scripts/verify_common.py).

Checks on a translated request (grades justified next to each check below):
  parse        every PromQL string parses (`$__rate_interval` substituted first)
  count        one PromQL string per displayed Datadog formula
  formula      the PromQL has the formula's shape: same operators, literals and operands in place
  aggregation  each query's Datadog space aggregator is the outermost aggregation of its subexpression
  grouping     `by {tags}` count == `by (labels)` count; labels consistent with agent0's `labels:` map
  rate         rate()/irate()/increase() only on monotonic sums; monotonic sums without rate() are a nit
  type         otel_metric_type agrees with the pinned OTel catalog / the dataset snapshot
  literal      no numeric constant that is not in the Datadog source (AGENTS.md)
  range        the only range is [$__rate_interval]; no subquery, offset, @, $__interval, $__range
  selector     every selector uses otel_metric_name= (bare metric names do not work in Dash0)
  grain        metrics with a pinned dedup grain (plan 05 Task 4) aggregate by it first; missing -> nit
A blocked request passes unless its error list is empty (the codes come from the deterministic overlay).

Usage:
  uv run scripts/lint_expected.py <service>/<dashboard_id> [...] [--mutations]
  uv run scripts/lint_expected.py --all [--mutations]
Writes fixtures/oracle/verify/<key>/lint.yaml, or with --mutations the verdicts on the known-bad
variants of scripts/mutate_expected.py to fixtures/oracle/verify/mutations/<key>.lint.yaml.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import math
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import promql_parser as pp
import yaml

import build_expected as be
import verify_common as vc

TOOL = "scripts/lint_expected.py"
RATE_INTERVAL = "[$__rate_interval]"
# `$__rate_interval` is a Grafana/Dash0 variable, not PromQL. It is replaced by this distinctive
# duration before parsing, so any other range in the AST is a range the expectation wrote itself.
SENTINEL = "4321ms"
SENTINEL_RANGE = dt.timedelta(milliseconds=4321)
RATE_FNS = frozenset({"rate", "irate", "increase"})
# Plan 05 Task 4: series that collector restarts duplicate (resource-hash churn) need an inner
# dedup aggregation by these labels before Datadog's space aggregation.
GRAIN_LABELS = {"postgresql.backends": ("service_instance_id",)}
DEFAULT_AGGREGATOR = "avg"  # Datadog's space aggregation when the query has no `agg:` prefix
BY_TAGS = re.compile(r"\}\s*by\s*\{([^}]*)\}")
# A number in Datadog text that is not part of a name (`system.load.15`, `query1`) or a variable.
DD_NUMBER = re.compile(r"(?<![\w.$])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")
FORBIDDEN = re.compile(r"\$__interval\b|\$__range\b|\boffset\b|@")
STRING = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`[^`]*`')


@dataclasses.dataclass(frozen=True)
class Finding:
    severity: str  # nit | block
    check: str
    message: str

    @property
    def reason(self) -> str:
        return f"{self.check}: {self.message}"


def verdict_of(findings: list[Finding]) -> str:
    return vc.worst([f.severity for f in findings])


# --------------------------------------------------------------------------- text helpers


def mask_strings(text: str) -> str:
    """`text` with the contents of every quoted string blanked (same length, quotes kept)."""
    return STRING.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], text)


def replace_outside_strings(text: str, old: str, new: str, count: int = 0) -> str:
    """Replace `old` by `new` where it does not sit inside a quoted string (all if count == 0)."""
    masked = mask_strings(text)
    starts = [m.start() for m in re.finditer(re.escape(old), masked)]
    if count:
        starts = starts[:count]
    for s in reversed(starts):
        text = text[:s] + new + text[s + len(old) :]
    return text


def dd_numbers(request: dict[str, Any]) -> list[float]:
    """Numeric constants written in the Datadog formulas and queries."""
    texts = [f or "" for f in request["formulas"]] + [q["query"] or "" for q in request["queries"]]
    return [float(n) for t in texts for n in DD_NUMBER.findall(t)]


def has_number(numbers: list[float], value: float) -> bool:
    return any(math.isclose(n, value, rel_tol=1e-9, abs_tol=0.0) for n in numbers)


def dd_aggregator(query: str) -> tuple[str, bool]:
    """(space aggregator, whether it is Datadog's default) of one Datadog metrics query."""
    m = be.AGGREGATOR.match(query)
    return (m.group(1), False) if m else (DEFAULT_AGGREGATOR, True)


def dd_tags(query: str) -> list[str]:
    m = BY_TAGS.search(query)
    return [t.strip() for t in m.group(1).split(",") if t.strip()] if m else []


def displayed_formulas(request: dict[str, Any]) -> list[str]:
    """The expressions Datadog displays: the non-empty formulas, else the single (first) query."""
    formulas = [f for f in request["formulas"] if f]
    if formulas:
        return formulas
    queries = request["queries"]
    return [queries[0]["name"] or "q"] if queries else []


# --------------------------------------------------------------------------- AST helpers


def parse_promql(text: str) -> tuple[Any, str | None]:
    """(AST, None) or (None, parser error), with `[$__rate_interval]` replaced by [SENTINEL]."""
    try:
        return pp.parse(replace_outside_strings(text, RATE_INTERVAL, f"[{SENTINEL}]")), None
    except Exception as exc:  # promql_parser raises ValueError; anything else is a parse failure too
        return None, str(exc).splitlines()[0] if str(exc) else type(exc).__name__


def children(node: Any) -> list[Any]:
    if isinstance(node, pp.BinaryExpr):
        return [node.lhs, node.rhs]
    if isinstance(node, pp.AggregateExpr):
        return [node.expr] + ([node.param] if node.param is not None else [])
    if isinstance(node, pp.Call):
        return list(node.args)
    if isinstance(node, (pp.ParenExpr, pp.UnaryExpr, pp.SubqueryExpr)):
        return [node.expr]
    if isinstance(node, pp.MatrixSelector):
        return [node.vector_selector]
    return []


def walk(node: Any, parents: tuple[Any, ...] = ()) -> Iterator[tuple[Any, tuple[Any, ...]]]:
    """Pre-order (node, ancestors) pairs."""
    yield node, parents
    for child in children(node):
        yield from walk(child, (*parents, node))


def unparen(node: Any) -> Any:
    while isinstance(node, pp.ParenExpr):
        node = node.expr
    return node


def matcher_value(vs: Any, name: str) -> str | None:
    for m in vs.matchers.matchers:
        if m.name == name and str(m.op) == "MatchOp.Equal":
            return str(m.value)
    return None


def group_labels(agg: Any) -> list[str]:
    return list(agg.modifier.labels) if agg.modifier is not None else []


def binary_ops(node: Any) -> list[str]:
    return [str(n.op) for n, _ in walk(node) if isinstance(n, pp.BinaryExpr)]


def short(node: Any, limit: int = 80) -> str:
    text = str(node)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# --------------------------------------------------------------------------- per-PromQL checks


def check_forbidden(text: str) -> list[Finding]:
    """`$__interval`/`$__range` are panel-dependent and `offset`/`@` shift time: none of them is in a
    plain Datadog query, so each one changes the numbers -> block."""
    masked = mask_strings(text)
    out = [Finding("block", "range", f"forbidden token {m.group(0)!r}") for m in FORBIDDEN.finditer(masked)]
    if SENTINEL in masked:
        out.append(Finding("block", "range", f"literal range {SENTINEL}"))
    return out


def check_selectors(expr: Any) -> list[Finding]:
    """A bare metric name or a selector without otel_metric_name selects nothing in Dash0 -> block.
    A missing otel_metric_type only risks mixing two instrument types under one name -> nit."""
    out = []
    for node, _ in walk(expr):
        if not isinstance(node, pp.VectorSelector):
            continue
        if node.name is not None:
            out.append(Finding("block", "selector", f"bare metric name {node.name!r}; use otel_metric_name="))
        if matcher_value(node, "otel_metric_name") is None:
            out.append(Finding("block", "selector", f"no otel_metric_name= matcher in {short(node)}"))
        elif matcher_value(node, "otel_metric_type") is None:
            out.append(Finding("nit", "selector", f"no otel_metric_type= matcher in {short(node)}"))
        if node.matchers.or_matchers:
            out.append(Finding("block", "selector", f"`or` matchers in {short(node)}"))
    return out


def check_types(expr: Any) -> list[Finding]:
    """A wrong otel_metric_type selects no series (or the wrong instrument) -> block. A type that only the
    dataset snapshot has, not the catalog, can be a receiver quirk -> nit."""
    catalog, dataset = be.otel_catalog(), be.dataset_metrics()
    out = []
    for node, _ in walk(expr):
        if not isinstance(node, pp.VectorSelector):
            continue
        name, typ = matcher_value(node, "otel_metric_name"), matcher_value(node, "otel_metric_type")
        if name is None or typ is None:
            continue
        seen = list(dataset.get(name) or [])
        if name in catalog:
            want = catalog[name]["type"]
            if typ == want:
                continue
            if typ in seen:
                out.append(Finding("nit", "type", f"{name} is {want} in the OTel catalog, dataset also has {typ}"))
            else:
                out.append(Finding("block", "type", f"{name} is {want} in the OTel catalog, PromQL selects {typ}"))
        elif seen:
            if typ not in seen:
                out.append(Finding("block", "type", f"{name} is {'/'.join(seen)} in the dataset, PromQL selects {typ}"))
        else:
            out.append(Finding("block", "type", f"{name} is neither in the OTel catalog nor in the dataset"))
    return out


def check_rate(expr: Any) -> list[Finding]:
    """rate()/irate()/increase() on a gauge or non-monotonic sum differentiates a level -> block.
    A monotonic counter shown without rate() is a cumulative total, rarely what Datadog shows (its
    counters arrive as per-interval counts or rates), but Agent0 sometimes argues for it -> nit."""
    catalog = be.otel_catalog()
    out = []
    for node, parents in walk(expr):
        if isinstance(node, pp.Call) and node.func.name in RATE_FNS:
            for arg in node.args:
                vs = arg.vector_selector if isinstance(arg, pp.MatrixSelector) else None
                if vs is None:
                    out.append(Finding("block", "rate", f"{node.func.name}() over {short(arg)}, not a range selector"))
                    continue
                name, typ = matcher_value(vs, "otel_metric_name"), matcher_value(vs, "otel_metric_type")
                if typ != "sum":
                    out.append(Finding("block", "rate", f"{node.func.name}() on {name} with otel_metric_type={typ}"))
                elif name in catalog and catalog[name]["monotonic"] is not True:
                    out.append(Finding("block", "rate", f"{node.func.name}() on non-monotonic sum {name}"))
        elif isinstance(node, pp.VectorSelector) and not (parents and isinstance(parents[-1], pp.MatrixSelector)):
            name = matcher_value(node, "otel_metric_name")
            if name in catalog and catalog[name]["type"] == "sum" and catalog[name]["monotonic"] is True:
                out.append(Finding("nit", "rate", f"monotonic counter {name} selected without rate()/increase()"))
    return out


def check_ranges(expr: Any) -> list[Finding]:
    """Any range but [$__rate_interval], a subquery, offset or @ changes the window -> block."""
    out = []
    for node, _ in walk(expr):
        if isinstance(node, pp.MatrixSelector) and node.range != SENTINEL_RANGE:
            out.append(Finding("block", "range", f"range [{pp.display_duration(node.range)}], only [$__rate_interval] is allowed"))
        elif isinstance(node, pp.SubqueryExpr):
            out.append(Finding("block", "range", f"subquery {short(node)}"))
        elif isinstance(node, pp.VectorSelector) and (node.offset is not None or node.at is not None):
            out.append(Finding("block", "range", f"offset/@ modifier on {short(node)}"))
    return out


def check_literals(expr: Any, numbers: list[float]) -> list[Finding]:
    """A constant the Datadog source does not contain is an invented unit conversion (AGENTS.md) -> block.
    Label matcher values are strings, not NumberLiterals, so they are never counted."""
    return [
        Finding("block", "literal", f"constant {node.val:g} is not in the Datadog source")
        for node, _ in walk(expr)
        if isinstance(node, pp.NumberLiteral) and not has_number(numbers, node.val)
    ]


# --------------------------------------------------------------------------- formula / aggregation / grouping


def align(formula: Any, promql: Any, out: list[tuple[str, Any]]) -> str | None:
    """Match the Datadog formula AST against the PromQL AST. A formula operand (`query1`) matches any
    PromQL subtree, which is recorded in `out`; operators and literals must match one to one.
    Returns None on success, else what differs."""
    f, p = unparen(formula), unparen(promql)
    if isinstance(f, pp.VectorSelector) and f.name and not f.matchers.matchers:
        out.append((f.name, p))
        return None
    if isinstance(f, pp.NumberLiteral):
        if isinstance(p, pp.NumberLiteral) and math.isclose(f.val, p.val):
            return None
        return f"formula constant {f.val:g} has no counterpart (PromQL has {short(p, 40)})"
    if isinstance(f, pp.BinaryExpr):
        if not isinstance(p, pp.BinaryExpr) or str(p.op) != str(f.op):
            return f"formula `{short(f, 40)}` vs PromQL `{short(p, 60)}`"
        return align(f.lhs, p.lhs, out) or align(f.rhs, p.rhs, out)
    if isinstance(f, pp.UnaryExpr):
        if not isinstance(p, pp.UnaryExpr):
            return f"formula `{short(f, 40)}` vs PromQL `{short(p, 60)}`"
        return align(f.expr, p.expr, out)
    return f"unsupported formula node `{short(f, 40)}`"


def outermost_aggregations(node: Any) -> tuple[list[Any], list[Any]]:
    """(aggregations not nested in another aggregation, selectors reached without any aggregation)."""
    node = unparen(node)
    if isinstance(node, pp.AggregateExpr):
        return [node], []
    if isinstance(node, (pp.VectorSelector, pp.MatrixSelector)):
        return [], [node]
    aggs: list[Any] = []
    bare: list[Any] = []
    for child in children(node):
        a, b = outermost_aggregations(child)
        aggs += a
        bare += b
    return aggs, bare


def check_query(query: dict[str, Any], sub: Any, labels_map: dict[str, Any] | None) -> list[Finding]:
    """One Datadog query against the PromQL subtree the formula alignment assigned to it."""
    name = query["name"] or "q"
    text = query["query"] or ""
    agg, default = dd_aggregator(text)
    tags = dd_tags(text)
    aggs, bare = outermost_aggregations(sub)
    out = []
    # Datadog always space-aggregates a query; a bare selector returns every raw series -> block.
    out += [Finding("block", "aggregation", f"{name}: selector {short(b, 60)} is not aggregated") for b in bare]
    if not aggs and not bare:
        out.append(Finding("block", "aggregation", f"{name}: no metric selected in `{short(sub, 60)}`"))
    if len(aggs) > 1:
        # One Datadog metric computed from several OTel aggregations (e.g. accepted - handled): not 1:1,
        # possibly right, needs a human (REVIEW.md C) -> nit.
        out.append(Finding("nit", "aggregation", f"{name}: derived from {len(aggs)} aggregations `{short(sub, 70)}`, not a 1:1 metric"))
    for a in aggs:
        op = str(a.op)
        if op != agg:
            # A different space aggregator gives different numbers whenever there is >1 series -> block.
            source = f"{agg} (Datadog default)" if default else agg
            out.append(Finding("block", "aggregation", f"{name}: Datadog aggregator {source}, PromQL {op}"))
        labels = group_labels(a)
        if a.modifier is not None and str(a.modifier.type) != "AggModifierType.By":
            out.append(Finding("block", "grouping", f"{name}: `without (...)` grouping, Datadog groups by {tags}"))
        elif len(labels) != len(tags):
            # Extra or missing group-by labels change the number of series -> block.
            claim = ""
            if labels_map:
                claim = "; answer labels: " + ", ".join(f"{t}->{labels_map.get(t)}" for t in tags if t in labels_map)
            out.append(Finding("block", "grouping", f"{name}: Datadog by {{{','.join(tags)}}}, PromQL by ({', '.join(labels)}){claim}"))
        out += check_label_map(name, tags, labels, labels_map)
        # An aggregation nested under the one that matches Datadog's (max(avg by (host) (...))) adds a
        # second space aggregation the source does not have. It can be a deliberate grain choice
        # (per-CPU series -> per-host), so it is a nit, not a block.
        out += [
            Finding("nit", "aggregation", f"{name}: nested aggregation `{short(n, 60)}` not in the source")
            for n, _ in walk(a.expr)
            if isinstance(n, pp.AggregateExpr)
        ]
    out += check_grain(name, aggs)
    # Functions other than rate() (label_replace, abs, ...) transform the series beyond the 1:1
    # mapping; translated requests have no Datadog function (the overlay blocks those) -> nit.
    out += [
        Finding("nit", "formula", f"{name}: function {n.func.name}() not in the Datadog source")
        for n, _ in walk(sub)
        if isinstance(n, pp.Call) and n.func.name not in RATE_FNS
    ]
    return out


def check_grain(name: str, aggs: list[Any]) -> list[Finding]:
    """A grain-pinned metric must sit under an aggregation that groups by its grain labels; without it
    a collector restart double-counts. Plan wants it, the expectation may still be accepted -> nit."""
    out = []
    for a in aggs:
        for node, parents in walk(a.expr):
            if not isinstance(node, (pp.VectorSelector, pp.MatrixSelector)):
                continue
            vs = node.vector_selector if isinstance(node, pp.MatrixSelector) else node
            metric = matcher_value(vs, "otel_metric_name")
            grain = GRAIN_LABELS.get(metric or "")
            if grain is None:
                continue
            inner = [p for p in parents if isinstance(p, pp.AggregateExpr)]
            if not any(set(grain) <= set(group_labels(p)) for p in inner):
                out.append(Finding("nit", "grain", f"{name}: {metric} has no dedup grain by ({', '.join(grain)}) (plan 05 Task 4)"))
    return out


def check_label_map(name: str, tags: list[str], labels: list[str], labels_map: dict[str, Any] | None) -> list[Finding]:
    """Agent0's `labels:` map is its own claim of tag -> label; using other labels is inconsistent but
    the map itself is unreviewed -> nit."""
    if labels_map is None:
        return []
    out = []
    for t in tags:
        mapped = labels_map.get(t)
        if mapped and mapped not in labels:
            out.append(Finding("nit", "grouping", f"{name}: answer maps tag {t} -> {mapped}, PromQL groups by ({', '.join(labels)})"))
    claimed = {v for v in labels_map.values() if v}
    for label in labels:
        if label not in claimed:
            out.append(Finding("nit", "grouping", f"{name}: label {label} is not in the answer's labels map"))
    return out


def check_formula(request: dict[str, Any], formula: str, expr: Any, labels_map: dict[str, Any] | None) -> list[Finding]:
    queries = {q["name"] or "q": q for q in request["queries"]}
    f_expr, err = parse_promql(formula)
    if f_expr is None:
        return [Finding("block", "formula", f"cannot parse Datadog formula {formula!r}: {err}")]
    pairs: list[tuple[str, Any]] = []
    diff = align(f_expr, expr, pairs)
    if diff is not None:
        missing = sorted(set(binary_ops(f_expr)) - set(binary_ops(expr)))
        if missing:
            # The formula's arithmetic is not computed at all -> block.
            return [Finding("block", "formula", f"operator(s) {' '.join(missing)} of `{formula}` missing in PromQL")]
        # Same operators, different shape: may be an equivalent rewrite, but aggregation and grouping
        # could not be checked per query -> block, a human has to look.
        return [Finding("block", "formula", f"shape differs from `{formula}`: {diff}")]
    out = []
    for qname, sub in pairs:
        if qname not in queries:
            out.append(Finding("block", "formula", f"formula `{formula}` references unknown query {qname}"))
        else:
            out += check_query(queries[qname], sub, labels_map)
    return out


# --------------------------------------------------------------------------- entry


def lint_translated(request: dict[str, Any], expected: dict[str, Any], labels_map: dict[str, Any] | None) -> list[Finding]:
    promql = list(expected.get("promql") or [])
    formulas = displayed_formulas(request)
    out = []
    if len(promql) != len(formulas):
        # Panels would show a different number of series than Datadog -> block.
        out.append(Finding("block", "count", f"{len(promql)} PromQL string(s) for {len(formulas)} displayed formula(s)"))
    numbers = dd_numbers(request)
    for i, text in enumerate(promql):
        tag = f"promql[{i}] " if len(promql) > 1 else ""
        found = check_forbidden(text)
        expr, err = parse_promql(text)
        if expr is None:
            found.append(Finding("block", "parse", f"does not parse: {err}"))
        else:
            found += check_selectors(expr) + check_types(expr) + check_rate(expr) + check_ranges(expr)
            found += check_literals(expr, numbers)
            if i < len(formulas):
                found += check_formula(request, formulas[i], expr, labels_map)
        out += [dataclasses.replace(f, message=tag + f.message) for f in found]
    return out


def lint_entry(
    request: dict[str, Any],
    expected: dict[str, Any],
    case: dict[str, Any],
    answer_item: dict[str, Any] | None,
) -> list[Finding]:
    """Findings for one request: `request` from the case, `expected` the entry's `expected` block."""
    outcome = expected.get("outcome")
    variables = {v["name"]: v for v in case.get("template_variables") or []}
    labels_map = answer_item.get("labels") if answer_item and isinstance(answer_item.get("labels"), dict) else None
    if outcome == "blocked":
        errors = list(expected.get("errors") or [])
        if not errors:
            return [Finding("block", "errors", "blocked without an error code")]
        # No source-text rule error means only the mapping lookup can block the request.
        derived = be.rule_errors(request, variables) or ["MISSING_METRIC_MAPPING"]
        if errors != derived:
            # The overlay derives the code from the source text; a different code (only possible via
            # overrides.yaml or hand edits) is worth a look but not wrong per se -> nit.
            return [Finding("nit", "errors", f"errors {errors}, the deterministic overlay derives {derived}")]
        return []
    if outcome != "translated":
        return [Finding("block", "outcome", f"unknown outcome {outcome!r}")]
    rules = be.rule_errors(request, variables)
    if rules:
        # The deterministic overlay (and the converter) block this request from its source text.
        return [Finding("block", "outcome", f"translated, but the overlay blocks it with {rules}")]
    out = lint_translated(request, expected, labels_map)
    warnings = sorted(expected.get("warnings") or [])
    derived_w = be.rule_warnings(request, variables)
    if warnings != derived_w:
        # Warnings are derived from the source text by build_expected; a drift is cosmetic -> nit.
        out.append(Finding("nit", "warnings", f"warnings {warnings}, the overlay derives {derived_w}"))
    return out


def result(source_path: str, findings: list[Finding]) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "verdict": verdict_of(findings),
        "reasons": list(dict.fromkeys(f.reason for f in findings)),
    }


# --------------------------------------------------------------------------- dashboards


def load_answers(key: str) -> dict[str, dict[str, Any]]:
    path = vc.ROOT / "fixtures" / "oracle" / "agent0" / key / "answer.yaml"
    if not path.is_file():
        return {}
    return {a["source_path"]: a for a in yaml.safe_load(path.read_text()) or []}


def lint_dashboard(key: str) -> list[dict[str, Any]]:
    """Results for every request of the case, in case order."""
    case, answers = vc.load_case(key), load_answers(key)
    entries = {e["source_path"]: e for e in vc.load_expected(key)["requests"]}
    out = []
    for req in case["requests"]:
        sp = req["source_path"]
        entry = entries.get(sp)
        if entry is None:
            out.append(result(sp, [Finding("block", "expected", "no expected.yaml entry for this request")]))
        else:
            out.append(result(sp, lint_entry(req, entry["expected"], case, answers.get(sp))))
    return out


def lint_mutations(key: str) -> list[dict[str, Any]]:
    """Results for every known-bad variant of the dashboard, keyed by the mutation id."""
    case, answers = vc.load_case(key), load_answers(key)
    requests = vc.case_requests(case)
    return [
        result(m["id"], lint_entry(requests[m["source_path"]], m["expected"], case, answers.get(m["source_path"])))
        for m in vc.load_mutations(key)
    ]


def display(path: Path) -> str:
    return str(path.relative_to(vc.ROOT)) if path.is_relative_to(vc.ROOT) else str(path)


def summary(results: list[dict[str, Any]]) -> str:
    return ", ".join(f"{sum(r['verdict'] == v for r in results)} {v}" for v in vc.VERDICTS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keys", nargs="*", metavar="SVC/ID")
    parser.add_argument("--all", action="store_true", help="every dashboard in fixtures/oracle/dashboards.json")
    parser.add_argument("--mutations", action="store_true", help="lint the known-bad variants instead")
    args = parser.parse_args(argv)
    keys = vc.all_keys() if args.all else args.keys
    if not keys:
        parser.error("give SVC/ID keys or --all")
    for key in keys:
        if args.mutations:
            results = lint_mutations(key)
            if not results:
                print(f"{key}: no mutations (run scripts/mutate_expected.py first)")
                continue
        else:
            results = lint_dashboard(key)
        path = vc.write_verdicts(key, "lint", results, {"tool": TOOL}, mutations=args.mutations)
        print(f"{display(path)}: {summary(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
