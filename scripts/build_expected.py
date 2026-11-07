"""Build fixtures/expected/<service>/<dashboard_id>/expected.yaml (development-time only).

Inputs, all in the repo:
  fixtures/cases/<key>.yaml                       deterministic case inventory
  fixtures/oracle/agent0/<key>/answer.yaml        Agent0 proposal (outcome + PromQL per request)
  fixtures/expected/<key>/overrides.yaml          human decisions (optional; wins over everything)

Agent0 proposes WHAT a request becomes (metric, matchers, aggregation). This script
adds the project's deterministic rules on top:
  * blocking rules that Agent0 cannot lift: no metrics query, any Datadog function
    (see ALLOWED_FUNCTIONS), and an OTel metric that exists neither in the `default` dataset
    snapshot (fixtures/oracle/dash0_default_metrics.yaml) nor in the pinned OTel catalog
    (fixtures/otel/catalog.yaml),
  * a `dataset` block for translations whose OTel metrics are defined but missing from the dataset
    (they stay translated; only the live check is impossible),
  * diagnostic codes derived from the source text (not from Agent0's prose),
  * warnings (template variables dropped, default aggregator applied),
  * widget and dashboard expectations derived from the request expectations,
  * milestones.
Nothing here is ever called by the converter or by the tests.

Usage: uv run scripts/build_expected.py <service>/<dashboard_id> [...]
"""

from __future__ import annotations

import functools
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Widget types the end-state converter renders (plans 04 + 05) and their Perses panel plugin.
PANEL_PLUGIN = {"timeseries": "TimeSeriesChart", "query_value": "StatChart", "note": "Markdown"}
# Every Datadog function blocks its request: wrapping ones (`top(`, `per_second(`) in plan 02,
# trailing ones (`.rollup()`, `.as_count()`) in plan 03 check 1, functions in formulas in plan 05
# Task 5. No plan lifts this for dashboards. A function may only move into this allowlist through
# its own plan task with an exact test; until then the list stays empty, whatever Agent0 proposes.
ALLOWED_FUNCTIONS: frozenset[str] = frozenset()
AGGREGATOR = re.compile(r"^(avg|sum|min|max):")
WRAPPING_FN = re.compile(r"^\s*([a-z_]+)\(")
TRAILING_FN = re.compile(r"\.([a-z_]+)\(")
FORMULA_FN = re.compile(r"\b([a-z_]+)\(")
VARIABLE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
METRIC_SELECTOR = re.compile(r'otel_metric_name="([^"]+)"(?:\s*,\s*otel_metric_type="([^"]+)")?')

P0_CASES = {("postgres/postgresql_dashboard", "widgets[1]")}


def milestone(key: str, widget_path: str) -> str:
    if (key, widget_path) in P0_CASES:
        return "p0"
    if key == "postgres/postgresql_dashboard":
        return "p1"
    return "p2"


def widget_path_of(source_path: str) -> str:
    return source_path.split(".definition.requests")[0]


def resolve(doc, path: str):
    node = doc
    for name, index in re.findall(r"\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]", path):
        node = node[name] if name else node[int(index)]
    return node


def rule_errors(request: dict) -> list[str]:
    """Deterministic error code for a blocked request, derived from the source text only."""
    queries = request["queries"]
    formulas = [f for f in request["formulas"] if f]
    if not queries or any(q.get("data_source") not in (None, "metrics") for q in queries):
        return ["UNSUPPORTED_DATA_SOURCE"]
    if any(FORMULA_FN.search(f) for f in formulas):
        return ["UNSUPPORTED_FORMULA"]
    for q in queries:
        text = q["query"] or ""
        if WRAPPING_FN.match(text) or TRAILING_FN.search(text):
            return ["UNSUPPORTED_QUERY_FUNCTION"]
    return ["MISSING_METRIC_MAPPING"]


def blocked_functions(request: dict) -> list[str]:
    """Datadog functions in the request's queries or formulas that are not allowlisted, sorted."""
    texts = [q["query"] or "" for q in request["queries"]] + [f or "" for f in request["formulas"]]
    return sorted({fn for t in texts for fn in FORMULA_FN.findall(t)} - ALLOWED_FUNCTIONS)


@functools.cache
def otel_catalog() -> dict:
    """Every metric OpenTelemetry defines in the pinned sources (scripts/build_otel_catalog.py)."""
    return yaml.safe_load((ROOT / "fixtures" / "otel" / "catalog.yaml").read_text())


@functools.cache
def dataset_metrics() -> dict:
    """Metric names present in the Dash0 `default` dataset snapshot -> types seen."""
    return yaml.safe_load((ROOT / "fixtures" / "oracle" / "dash0_default_metrics.yaml").read_text())["metrics"]


def metric_availability(promql: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Split the OTel metrics used in `promql` into (not defined anywhere, defined but not in the
    dataset, type mismatches against the catalog for metrics outside the dataset)."""
    catalog, present = otel_catalog(), dataset_metrics()
    used = sorted({(m, t) for q in promql for m, t in METRIC_SELECTOR.findall(q)})
    names = sorted({m for m, _ in used})
    undefined = [m for m in names if m not in present and m not in catalog]
    absent = [m for m in names if m not in present and m in catalog]
    mismatched = sorted(
        f"{m} is {catalog[m]['type']} in {catalog[m]['sources'][0]}, PromQL selects {t}"
        for m, t in used
        if m in absent and t and t != catalog[m]["type"]
    )
    return undefined, absent, mismatched


def rule_warnings(request: dict, variables: dict[str, dict]) -> list[str]:
    warnings = []
    for q in request["queries"]:
        text = q["query"] or ""
        for name in VARIABLE.findall(text):
            if name in variables and variables[name].get("default") in (None, "*"):
                warnings.append("TEMPLATE_VARIABLE_DROPPED")
        if not AGGREGATOR.match(text) and not WRAPPING_FN.match(text):
            warnings.append("DEFAULT_AGGREGATOR_APPLIED")
    return sorted(warnings)


def build(key: str) -> dict:
    case = yaml.safe_load((ROOT / "fixtures" / "cases" / f"{key}.yaml").read_text())
    answer_path = ROOT / "fixtures" / "oracle" / "agent0" / key / "answer.yaml"
    answers = {a["source_path"]: a for a in yaml.safe_load(answer_path.read_text())}
    overrides_path = ROOT / "fixtures" / "expected" / key / "overrides.yaml"
    overrides = yaml.safe_load(overrides_path.read_text()) if overrides_path.exists() else {}
    overrides = overrides or {}
    source = json.loads((ROOT / case["source"]["fixture"]).read_text())
    variables = {v["name"]: v for v in case["template_variables"]}
    service = case["service"]

    requests_out = []
    by_widget: dict[str, list[dict]] = {}
    for req in case["requests"]:
        sp = req["source_path"]
        agent = answers.get(sp)
        entry = {
            "source_path": sp,
            "milestone": milestone(key, widget_path_of(sp)),
            "reviewed": False,
            "provenance": {"kind": "agent0", "ref": str(answer_path.relative_to(ROOT))},
            "live_check": {"agent0": (agent or {}).get("live_check", "not run")},
        }
        notes = []
        if agent is None:
            outcome, promql = "blocked", []
            notes.append("no Agent0 answer for this request")
        else:
            outcome, promql = agent["outcome"], list(agent.get("promql") or [])
        functions = blocked_functions(req)
        if outcome == "translated" and not req["queries"]:
            notes.append("rule overlay: Agent0 translated a request without a metrics query")
            outcome, promql = "blocked", []
        elif outcome == "translated" and functions:
            notes.append(
                f"rule overlay: Datadog function(s) {', '.join(functions)} block the request (plans 02/03/05);"
                f" Agent0's translation is discarded: {' ; '.join(promql)}"
            )
            outcome, promql = "blocked", []
        elif outcome == "translated":
            undefined, absent, mismatched = metric_availability(promql)
            if undefined:
                notes.append(
                    f"rule overlay: metric(s) {', '.join(undefined)} exist neither in dataset `default` nor in the"
                    f" pinned OTel catalog (fixtures/otel/catalog.yaml); Agent0's translation is discarded: {' ; '.join(promql)}"
                )
                outcome, promql = "blocked", []
            elif absent:
                entry["dataset"] = {
                    "available": False,
                    "missing_metrics": absent,
                    "otel_sources": sorted({s for m in absent for s in otel_catalog()[m]["sources"]}),
                }
                notes.append(
                    f"OTel metric(s) {', '.join(absent)} are defined by OpenTelemetry but not present in dataset"
                    " `default`; the translation stands, but it cannot be live-checked"
                )
                notes.extend(f"type mismatch: {m}" for m in mismatched)
        expected = {"outcome": outcome}
        if outcome == "translated":
            expected["promql"] = promql
            expected["errors"] = []
            expected["warnings"] = rule_warnings(req, variables)
        else:
            expected["errors"] = rule_errors(req)
        entry["expected"] = expected
        if notes:
            entry["notes"] = notes
        override = overrides.get(sp)
        if override:
            entry.update({k: v for k, v in override.items() if k != "expected"})
            entry["expected"].update(override.get("expected", {}))
            entry["provenance"] = {"kind": "human", "ref": str(overrides_path.relative_to(ROOT))}
        requests_out.append(entry)
        by_widget.setdefault(widget_path_of(sp), []).append(entry)

    widgets_out = []
    for i, widget in enumerate(source.get("widgets", [])):
        definition = widget.get("definition", {})
        children = (
            [(f"widgets[{i}].definition.widgets[{j}]", f"widget-{i}-{j}", c) for j, c in enumerate(definition.get("widgets", []))]
            if definition.get("type") == "group"
            else [(f"widgets[{i}]", f"widget-{i}", widget)]
        )
        for path, panel_key, w in children:
            wdef = w.get("definition", {})
            wtype = wdef.get("type")
            reqs = by_widget.get(path, [])
            supported = wtype in PANEL_PLUGIN
            translated = supported and all(r["expected"]["outcome"] == "translated" for r in reqs)
            if wtype == "note":
                translated = True
            expected = {"outcome": "translated" if translated else "blocked"}
            if translated:
                expected.update(
                    panel_key=panel_key,
                    title=wdef.get("title", ""),
                    panel_plugin=PANEL_PLUGIN[wtype],
                    promql=[q for r in reqs for q in r["expected"]["promql"]],
                    errors=[],
                    warnings=sorted(c for r in reqs for c in r["expected"].get("warnings", [])),
                )
            else:
                errs = ["UNSUPPORTED_WIDGET"] if not supported else sorted(
                    c for r in reqs for c in r["expected"]["errors"]
                )
                expected["errors"] = errs
            widgets_out.append(
                {
                    "source_path": path,
                    "type": wtype,
                    "milestone": milestone(key, path),
                    "reviewed": all(r["reviewed"] for r in reqs) if reqs else False,
                    "expected": expected,
                }
            )

    n_translated = sum(w["expected"]["outcome"] == "translated" for w in widgets_out)
    dash_outcome = "blocked" if n_translated == 0 else ("translated" if n_translated == len(widgets_out) else "partial")
    dashboard = {
        "milestone": "p1" if service == "postgres" else "p2",
        "reviewed": all(w["reviewed"] for w in widgets_out),
        "expected": {
            "outcome": dash_outcome,
            "widgets": [
                {
                    "source_path": w["source_path"],
                    "outcome": w["expected"]["outcome"],
                    **({"panel_key": w["expected"]["panel_key"], "promql": w["expected"]["promql"]} if w["expected"]["outcome"] == "translated" else {}),
                }
                for w in widgets_out
            ],
        },
    }

    return {
        "source_fixture": case["source"]["fixture"],
        "mapping": f"mappings/datadog/{service}.json",
        "project": "datadog-migration",
        "requests": requests_out,
        "widgets": widgets_out,
        "dashboard": dashboard,
    }


HEADER = """\
# GENERATED by scripts/build_expected.py from Agent0's answer + project rules. Do not edit by hand:
# put human decisions (corrections, `reviewed: true`) in overrides.yaml next to this file, keyed
# by request source_path, then re-run the script.
# Expectations describe the END STATE with the complete, human-reviewed mapping file named below.
# `milestone` says when a case must turn green. Unreviewed cases are skipped by default.
"""


def write(key: str) -> tuple[Path, dict]:
    out = ROOT / "fixtures" / "expected" / key / "expected.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build(key)
    out.write_text(HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000))
    return out, data


def main() -> int:
    for key in sys.argv[1:]:
        out, data = write(key)
        reqs = data["requests"]
        print(
            f"{out.relative_to(ROOT)}: {sum(r['expected']['outcome'] == 'translated' for r in reqs)}/{len(reqs)} requests translated, "
            f"dashboard {data['dashboard']['expected']['outcome']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
