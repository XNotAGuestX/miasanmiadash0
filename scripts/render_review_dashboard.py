"""Render one expected.yaml as a Perses dashboard for HUMAN review of the oracle (issue #87).

Development time only. The dashboard shows the agent0-derived expectation
(fixtures/expected/<svc>/<id>/expected.yaml), not converter output: nothing under src/ is
involved and the converter never reads anything written here (AGENTS.md).

Per dashboard:
  * one panel per translated REQUEST (not per widget), one PrometheusTimeSeriesQuery per expected
    PromQL; StatChart for query_value widgets, TimeSeriesChart otherwise,
  * panel title `[<priority>] <widget title> · <source_path>`, priority from scripts/triage.py
    (`unverified` when triage is not importable),
  * panel description: the Datadog queries and formulas, agent0's notes and the triage signals,
  * one full-width Markdown panel last, listing the blocked requests.

Output is a run directory in the format `migrator publish <dir>` consumes (PR #81:
src/migrator/convert.py, report.py, write.py, publish.py):

  <out>/<svc>/<id>/manifest.json
  <out>/<svc>/<id>/dashboards/oracle-review-<svc>-<id>.json

Deterministic: sorted keys, stable panel keys (req-<n>), no timestamps.

Usage: uv run scripts/render_review_dashboard.py <svc>/<id> [...] | --all [--out out/oracle-review]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from verify_common import ROOT, all_keys, load_case, load_expected, request_context

PROJECT = "oracle-review"
NAME_PREFIX = "oracle-review-"
DEFAULT_OUT = ROOT / "out" / "oracle-review"
DURATION = "1h"
# The only window with receiver data in the Dash0 `default` dataset (UTC).
WINDOW_START = "2026-11-07T14:05:00Z"
WINDOW_END = "2026-11-07T15:21:00Z"
UNVERIFIED = "unverified"

GRID_COLUMNS = 24
PANEL_WIDTH = 12
PANEL_HEIGHT = 8
TITLE_MAX = 60  # characters of the widget title kept in a panel title (source_path is never cut)

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase, [a-z0-9-] only, no leading/trailing/double dashes."""
    return _NON_SLUG.sub("-", text.lower()).strip("-")


def dashboard_name(key: str) -> str:
    return slugify(NAME_PREFIX + key)


def stable_json(value: Any) -> str:
    """Same serialization as migrator.write.stable_stringify (PR #81)."""
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- inputs


def load_priorities(key: str) -> dict[str, dict[str, Any]]:
    """triage.priorities(key), or {} when scripts/triage.py (or the function) is not importable."""
    try:
        import triage  # type: ignore[import-not-found]

        priorities = triage.priorities
    except (ImportError, AttributeError):
        return {}
    return dict(priorities(key) or {})


def agent0_items(key: str) -> dict[str, dict[str, Any]]:
    """agent0's answer items keyed by source_path, or {} when there is no answer file."""
    path = ROOT / "fixtures" / "oracle" / "agent0" / key / "answer.yaml"
    if not path.is_file():
        return {}
    items = yaml.safe_load(path.read_text()) or []
    return {i["source_path"]: i for i in items if isinstance(i, dict) and "source_path" in i}


# --------------------------------------------------------------------------- text


def _triage(priorities: dict[str, dict[str, Any]], source_path: str) -> dict[str, Any]:
    """{priority, signals, reasons, untrusted} of one request; `unverified` when triage has nothing."""
    p = priorities.get(source_path) or {}
    return {
        "priority": str(p.get("priority") or UNVERIFIED),
        "signals": dict(p.get("signals") or {}),
        "reasons": dict(p.get("reasons") or {}),
        "untrusted": list(p.get("untrusted") or []),
    }


def _triage_lines(t: dict[str, Any]) -> list[str]:
    signals = t["signals"]
    text = ", ".join(f"{v}={signals[v]}" for v in sorted(signals)) if signals else "none (no verifier has run)"
    lines = [f"Triage: {t['priority']}; signals: {text}"]
    if t["untrusted"]:
        lines.append("Untrusted verifiers (ignored for the priority): " + ", ".join(t["untrusted"]))
    lines += [f"- {v}: {'; '.join(t['reasons'][v])}" for v in sorted(t["reasons"])]
    return lines


def _notes(entry: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if answer.get("notes"):
        out.append(f"agent0: {answer['notes']}")
    out += [f"rule: {n}" for n in entry.get("notes") or []]
    return out


def _datadog_lines(ctx: dict[str, Any]) -> list[str]:
    lines = [f"Datadog widget: {ctx['widget']}"]
    lines += [f"- {name}: `{query}`" for name, query in ctx["queries"].items()]
    lines.append("Formulas: " + (", ".join(f"`{f}`" for f in ctx["formulas"]) or "none"))
    tvars = ", ".join(f"${v['name']} (default {v['default']})" for v in ctx["template_variables"])
    if tvars:
        lines.append(f"Template variables: {tvars}")
    return lines


def panel_description(
    ctx: dict[str, Any], entry: dict[str, Any], answer: dict[str, Any], triage: dict[str, Any]
) -> str:
    exp = entry["expected"]
    lines = [f"Source: {ctx['source_path']}", *_datadog_lines(ctx), ""]
    if exp.get("warnings"):
        lines.append("Expected warnings: " + ", ".join(exp["warnings"]))
    live = (entry.get("live_check") or {}).get("agent0")
    if live:
        lines.append(f"agent0 live check: {live}")
    dataset = entry.get("dataset") or {}
    if dataset.get("available") is False:
        lines.append("Not in the Dash0 dataset: " + ", ".join(dataset.get("missing_metrics") or []))
    lines += [f"Note - {n}" for n in _notes(entry, answer)]
    lines += _triage_lines(triage)
    return "\n".join(lines)


def blocked_markdown(
    blocked: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> str:
    if not blocked:
        return "## Blocked requests\n\nNone: every request of this dashboard is expected to translate.\n"
    parts = [f"## Blocked requests ({len(blocked)})\n"]
    for ctx, entry, answer, triage in blocked:
        parts.append(f"### [{triage['priority']}] {ctx['source_path']}\n")
        parts += [f"{line}  " for line in _datadog_lines(ctx)]
        parts.append("")
        parts.append("Errors: " + ", ".join(f"`{e}`" for e in entry["expected"].get("errors") or []) + "  ")
        parts += [f"- {n}" for n in _notes(entry, answer)]
        parts.append("")
        parts += [f"{line}  " for line in _triage_lines(triage)]
        parts.append("")
    return "\n".join(parts)


# --------------------------------------------------------------------------- render


def _query(promql: str) -> dict[str, Any]:
    return {
        "kind": "TimeSeriesQuery",
        "spec": {"plugin": {"kind": "PrometheusTimeSeriesQuery", "spec": {"query": promql}}},
    }


def _grid_item(key: str, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    return {"x": x, "y": y, "width": width, "height": height, "content": {"$ref": f"#/spec/panels/{key}"}}


def render(key: str, priorities: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The Perses review dashboard for one case key `<svc>/<id>`."""
    case = load_case(key)
    expected = load_expected(key)
    answers = agent0_items(key)
    prio = load_priorities(key) if priorities is None else priorities
    entries = {e["source_path"]: e for e in expected["requests"]}

    panels: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    blocked = []
    for r in case["requests"]:  # stable order = case request order
        sp = r["source_path"]
        entry = entries.get(sp)
        if entry is None:
            continue
        ctx = request_context(case, sp)
        answer = answers.get(sp, {})
        triage = _triage(prio, sp)
        if entry["expected"]["outcome"] != "translated":
            blocked.append((ctx, entry, answer, triage))
            continue
        n = len(items)
        pkey = f"req-{n}"
        title = f"[{triage['priority']}] {_truncate(r['widget_title'] or r['widget_type'], TITLE_MAX)} · {sp}"
        plugin: dict[str, Any] = (
            {"kind": "StatChart", "spec": {"calculation": "last-number"}}
            if r["widget_type"] == "query_value"
            else {"kind": "TimeSeriesChart", "spec": {}}
        )
        panels[pkey] = {
            "kind": "Panel",
            "spec": {
                "display": {"name": title, "description": panel_description(ctx, entry, answer, triage)},
                "plugin": plugin,
                "queries": [_query(q) for q in entry["expected"].get("promql") or []],
            },
        }
        items.append(_grid_item(pkey, (n % 2) * PANEL_WIDTH, (n // 2) * PANEL_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT))

    rows = (len(items) + 1) // 2
    panels["blocked"] = {
        "kind": "Panel",
        "spec": {
            "display": {"name": f"Blocked requests ({len(blocked)})", "description": ""},
            "plugin": {"kind": "Markdown", "spec": {"text": blocked_markdown(blocked)}},
            "queries": [],
        },
    }
    items.append(_grid_item("blocked", 0, rows * PANEL_HEIGHT, GRID_COLUMNS, min(4 + 4 * len(blocked), 40)))

    description = (
        f"Human review of the agent0-derived oracle fixtures/expected/{key}/expected.yaml "
        f"({case['title']}). Not converter output; triage signals are never approval. "
        f"Review window (only data in the Dash0 default dataset): {WINDOW_START} to {WINDOW_END} UTC."
    )
    return {
        "kind": "Dashboard",
        "metadata": {"name": dashboard_name(key), "project": PROJECT},
        "spec": {
            "display": {"name": f"Oracle review: {key}", "description": description},
            "duration": DURATION,
            "variables": [],
            "panels": panels,
            "layouts": [{"kind": "Grid", "spec": {"items": items}}],
        },
    }


def write_run(key: str, dashboard: dict[str, Any], out_root: Path) -> Path:
    """Write <out_root>/<key>/ as a `migrator publish` run directory; return the directory."""
    run = out_root / key
    rel = f"dashboards/{dashboard['metadata']['name']}.json"
    data = stable_json(dashboard).encode("utf-8")
    (run / "dashboards").mkdir(parents=True, exist_ok=True)
    (run / rel).write_bytes(data)
    manifest = {
        "manifestVersion": 1,
        "provider": PROJECT,
        "compilerVersion": "scripts/render_review_dashboard.py",
        "format": "json",
        "entries": [
            {
                "path": rel,
                "kind": "dashboard",
                "sourceId": f"fixtures/expected/{key}/expected.yaml",
                "sha256": hashlib.sha256(data).hexdigest(),
                "outcome": "translated",
                "eligible": True,
            }
        ],
    }
    (run / "manifest.json").write_bytes(stable_json(manifest).encode("utf-8"))
    return run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("keys", nargs="*", metavar="<svc>/<id>")
    ap.add_argument("--all", action="store_true", help="every case in fixtures/oracle/dashboards.json")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output root (default out/oracle-review)")
    args = ap.parse_args(argv)
    keys = all_keys() if args.all else args.keys
    if not keys or (args.all and args.keys):
        ap.error("give <svc>/<id> keys or --all")
    missing = [k for k in keys if not (ROOT / "fixtures" / "expected" / k / "expected.yaml").is_file()]
    if missing:
        ap.error("no expected.yaml for: " + ", ".join(missing))
    for key in keys:
        run = write_run(key, render(key), args.out)
        print(f"wrote {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
