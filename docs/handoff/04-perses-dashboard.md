# 04 — Datadog dashboard → Perses dashboard: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The core converter. `convert` turns Datadog timeseries widgets into a valid Perses dashboard, with per-widget outcomes. For the pinned "Postgres - Metrics" dashboard and `mappings/datadog/postgres.json`, it emits `dashboards/postgres-metrics.json` with the Connections panel, and reports the other 8 widgets with exact reasons. **This plan completes the MVP converter.**

**Architecture:**

- `dashboard.py` walks the top-level widgets.
- For each widget it runs the widget-level checks first: type, option keys, data source and formulas. Only then does it parse (plan 02) and compile (plan 03) each displayed query.
- A widget is all or nothing. Translated widgets become Perses panels in a 24-column Grid.
- `validation.py` checks the emitted object with a strict pydantic model and checks every PromQL string with `promql-parser` (Python bindings for the Rust port of the Prometheus parser).

**Tech Stack:** Python 3.13 (uv), pydantic, `promql-parser`, pytest.

**Spec:** [00-context.md](00-context.md) §6 (golden dashboard table), §7 (Perses shape) and §8 (outcomes and codes).

**Depends on:** plans 01–03.

## Global Constraints

- The panel key is `widget-<i>`, where `i` is the top-level widget index. `content.$ref` is `#/spec/panels/widget-<i>`.
- The panel plugin is exactly `{kind: "TimeSeriesChart", spec: {}}`. The query plugin is `PrometheusTimeSeriesQuery`, with only `query` set.
- `metadata` is `{name: <slug>, project: <--project>}`. `spec.duration` is `"1h"` and `spec.variables` is `[]`.
- Layout:
  - **Every top-level widget has `layout`:** Perses `x = 2·x`, `width = 2·width`, `y = y`, `height = height`.
  - **Otherwise:** the k-th translated panel goes at `x = (k % 2)·12`, `y = ⌊k/2⌋·8`, `width = 12`, `height = 8`.
  - Either way, emit `LAYOUT_APPROXIMATED` (info) once per dashboard, at `sourcePath: "widgets"`.
- Dashboard outcome:
  - every widget translated → `translated`;
  - at least one translated → `partial`;
  - none translated → `blocked`, with **no dashboard artifact**.
- The dashboard is never written if pydantic validation or the PromQL syntax check fails. That's an internal bug: emit `TARGET_VALIDATION_FAILED` and block the dashboard.

## Allowed source keys

These are evaluated per widget, before any query is compiled.

| Level | Silently used | Ignored with `OPTION_IGNORED` (info) | Anything else |
|---|---|---|---|
| `definition` | `type`, `title`, `requests` | `title_size`, `title_align`, `show_legend`, `legend_size`, `legend_layout`, `legend_columns`, `yaxis`, `markers`, `custom_links` | `UNSUPPORTED_WIDGET`: `Widget option '<key>' is not supported.` (for example, `time` changes the data window) |
| request | `queries`, `formulas`, `q`, `response_format` | `style`, `display_type`, `on_right_yaxis`, `metadata` | `UNSUPPORTED_WIDGET` |
| query | `data_source`, `name`, `query` | `semantic_mode` | `UNSUPPORTED_WIDGET` |

## Review Focus

1. **A formula that isn't a bare query name** (`query2 - query1`): block the whole widget. Never emit only the identity series. Covered by `blocks arithmetic formulas` (Task 1).
2. **A widget-specific time window** (`definition.time`): block it, because silently using the dashboard window changes the data. Covered by `blocks unknown widget options` (Task 1).
3. **A dashboard where every widget is blocked:** report it `blocked` and write no dashboard file. Covered by `overview screenboard is blocked without artifact` (Task 4).
4. **A Datadog title with characters outside `[a-z0-9]`:** the slug is stable and the file name is safe. Covered in plan 01 (`slugifies titles`), and asserted again here through `dashboards/postgres-metrics.json` existing (Task 4).
5. **Two dashboards with the same title in one run:** distinct files `x.json` and `x-2.json`, assigned in `sourceId` order. Covered by `duplicate titles get distinct slugs` (Task 3).

---

### Task 1: compileDashboard

**Files:**
- Create: `src/migrator/source/datadog/dashboard.py`
- Create: `fixtures/datadog/synthetic/dashboards/{supported.json,unsupported.json,layout.json}`
- Test: `tests/datadog/test_dashboard.py`

**Interfaces:**
- Consumes: `SourceAsset` and `CompileOptions` (plan 01), `parseMetricQuery` (plan 02), `compileMetricQuery`, `TemplateVariable` and `DatadogMapping` (plan 03).
- Produces:

```ts
export interface DashboardCompilation { dashboard: PersesDashboard | null; items: ItemResult[]; diagnostics: Diagnostic[] }
export function readTemplateVariables(body: Record<string, unknown>): TemplateVariable[];
// default = `default` ?? (defaults.length === 1 ? defaults[0] : null if absent, otherwise the JSON of the array)
export function compileDashboard(asset: SourceAsset, slug: string, mapping: DatadogMapping, options: CompileOptions): DashboardCompilation;
```

**Query source paths:**

- new format: `widgets[i].definition.requests[j].queries[k].query`;
- legacy format: `widgets[i].definition.requests[j].q`.

**Displayed queries per request:**

- If `formulas` is present, use formula order. Each formula must equal a query `name` in the same request; otherwise emit `UNSUPPORTED_FORMULA` at `...formulas[f].formula`, with `sourceText`.
- If `formulas` is absent, use query order.
- Legacy `q` is a single displayed query.

**Synthetic fixtures** (each about 20 lines):

- `supported.json`: 2 timeseries widgets, one legacy `q` and one new format. Both use `avg:postgresql.connections{*}`.
- `unsupported.json`: these widgets, in order:
  - a `toplist`;
  - a timeseries whose query has `data_source: "logs"`;
  - a timeseries with formula `query1 * 100`;
  - a timeseries with `definition.time: {live_span: "1h"}`;
  - a timeseries with query `avg:postgresql.connections{*}.rollup(max)`.
- `layout.json`: 2 timeseries widgets, both with `layout` (`{x:0,y:0,width:4,height:2}` and `{x:4,y:0,width:8,height:2}`), and a top-level `group` widget.

- [ ] **Step 1: Write the failing tests.** Use an inline reviewed mapping for `postgresql.connections`, as in plan 03.
  - `translates supported widgets`, on `supported.json`:
    - `items` are `[dashboard translated, widget translated, widget translated]`;
    - the panel keys are `["widget-0", "widget-1"]`;
    - both queries are `'avg ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})'`;
    - the grid items are `[{x:0,y:0,width:12,height:8}, {x:12,y:0,width:12,height:8}]`, plus their `$ref`s.
  - `blocks unsupported widgets with exact codes`, on `unsupported.json`:
    - the dashboard is `blocked` and `dashboard` is `null`;
    - the error codes per widget index are `0: UNSUPPORTED_WIDGET`, `1: UNSUPPORTED_DATA_SOURCE`, `2: UNSUPPORTED_FORMULA`, `3: UNSUPPORTED_WIDGET`, `4: UNSUPPORTED_QUERY_FUNCTION`.
  - `blocks arithmetic formulas`: in widget 2's diagnostic, `sourcePath` is `"widgets[2].definition.requests[0].formulas[0].formula"` and `sourceText` is `"query1 * 100"`.
  - `blocks unknown widget options`: widget 3's message is `"Widget option 'time' is not supported."`.
  - `uses source layout when every widget has one`, on `layout.json`:
    - the dashboard is `partial`, because the `group` is blocked;
    - the grid items are `[{x:0,y:0,width:8,height:2}, {x:8,y:0,width:16,height:2}]`.
    - Note: in `layout.json` the group also has a layout, so every widget has one.
  - `reads template variable defaults`: `readTemplateVariables({template_variables: [{name: "db", prefix: "db", defaults: ["*"]}]})` gives `[{name: "db", prefix: "db", default: "*"}]`.
- [ ] **Step 2: Run it.** Run `uv run migrator test tests/datadog/test_dashboard.py`. It must FAIL.
- [ ] **Step 3: Implement `readTemplateVariables` and `compileDashboard`** in `src/migrator/source/datadog/dashboard.py`, following the rules and tables above.
- [ ] **Step 4: Verify.** The tests must PASS.
- [ ] **Step 5: Commit.** `git add src fixtures/datadog/synthetic tests && git commit -m "feat: compile Datadog timeseries widgets to Perses panels"`.

### Task 2: Output validation

**Files:**
- Create: `src/migrator/validation.py`
- Modify: `pyproject.toml`, `uv.lock` (`uv add promql-parser`; already present if plan 01 added it)
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces:
  - `export function validateDashboard(d: unknown): string[]`. It returns an empty array when the object matches a strict pydantic model (`extra="forbid"`) of `PersesDashboard` (plan 01 types).
  - `export function checkPromqlSyntax(expr: string): string | null`. It returns `null` when the expression parses cleanly, or `syntax error: <parser message>`.

- [ ] **Step 1: Write the failing tests.**
  - `checkPromqlSyntax('avg by (a) ({otel_metric_name="x", otel_metric_type="sum"})')` is `null`.
  - `checkPromqlSyntax("avg by (a) (")` matches `/syntax error/`.
  - `checkPromqlSyntax('rate({otel_metric_name="x"}[$__rate_interval])')` is `null`.
  - `validateDashboard(<supported.json output from Task 1>)` is `[]`.
  - `validateDashboard({kind: "Dashboard"})` isn't empty.
- [ ] **Step 2: Run it.** It must FAIL.
- [ ] **Step 3: Implement it.**
  - Parse with `promql_parser.parse(text)`; it raises a `ValueError` on a syntax error, which is the failure.
  - Before parsing (for the check only), replace `$__rate_interval`, `$__interval` and `$__range` with `5m`, and `$__threshold` with `0`.
- [ ] **Step 4: Verify.** It must PASS.
- [ ] **Step 5: Commit.** `git commit -am "feat: validate emitted Perses dashboards and PromQL syntax"`. Add the new files first.

### Task 3: Wiring into the provider and the writers

**Files:**
- Modify: `src/migrator/source/datadog/__init__.py` (replace the skeleton's dashboard branch), `src/migrator/convert.py`, `src/migrator/report.py`
- Test: `tests/test_convert.py` (extend)

**Interfaces:**
- Consumes: `compileDashboard`, `validateDashboard`, `checkPromqlSyntax` and `assignSlugs` (plan 01).
- Produces:
  - `CompileResult.dashboards` filled.
  - `dashboards/<slug>.json|yaml` written.
  - Manifest entries `{kind: "dashboard", outcome, eligible: outcome === "translated"}`.
  - `report.validation`:
    - `syntax` is `passed` if every emitted PromQL string passed, `failed` if any failed, and `not_run` if nothing was emitted;
    - `schema` follows the same rule using `validateDashboard`;
    - `api` and `semantics` stay `not_run`.
- Monitors stay on the skeleton (`UNSUPPORTED_MONITOR_TYPE`) until plan 06.
- Replace the skeleton assertions in `tests/test_provider.py` (plan 01 Task 5) with assertions of real outcomes. The goldens use only the `dashboards/` folder, so later monitor work can't change them.

- [ ] **Step 1: Write the failing tests.**
  - `writes a dashboard per non-blocked source dashboard`: running `supported.json` + `unsupported.json` writes `dashboards/` containing exactly one file.
  - `duplicate titles get distinct slugs`:
    - Two copies of `supported.json`, placed in different subfolders of a temporary input folder, give `dashboards/<slug>.json` and `dashboards/<slug>-2.json`.
    - The slugs are assigned in `sourceId` order.
  - `yaml format writes .yaml`: with `--format yaml`, the dashboard file ends in `.yaml` and parses back to the same object as the JSON run.
- [ ] **Step 2: Run them.** They must FAIL. **Step 3: Implement.** **Step 4: Verify.** `uv run migrator check` must pass.
- [ ] **Step 5: Commit.** `git commit -am "feat: write Perses dashboards from convert"`.

### Task 4: Golden Postgres run

**Files:**
- Create: `fixtures/expected/postgres-p0/` (the full `--out` tree except `source/`)
- Test: `tests/test_golden.py`

**Interfaces:**
- Consumes: the full `convert` pipeline, the pinned postgres fixtures, and `mappings/datadog/postgres.json`.

- [ ] **Step 1: Write the failing test `postgres golden matches expected`.**
  - Run `runConvert({source: "datadog", inputs: ["fixtures/datadog/integrations-core/postgres/dashboards"], mapping: "mappings/datadog/postgres.json", out: tmp, format: "json", project: "datadog-migration"})`.
  - Assert `exitCode === 2`.
  - The dashboard "Postgres - Metrics" item is `partial`; "Postgres - Overview" is `blocked`.
  - The `dashboards/` folder contains exactly `["postgres-metrics.json"]`.
  - `panels["widget-1"].spec.queries[0].spec.plugin.spec.query` is `'avg by (postgresql_database_name) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})'`.
  - The non-info error codes per "Metrics" widget are:
    - widget 0: `MISSING_METRIC_MAPPING`×4
    - widget 1: none (warnings `UNREVIEWED_MAPPING` and `TEMPLATE_VARIABLE_DROPPED`)
    - widget 2: `MISSING_AGGREGATOR`×3
    - widget 3: `MISSING_METRIC_MAPPING`
    - widget 4: `MISSING_AGGREGATOR`×3
    - widget 5: `MISSING_AGGREGATOR`×6
    - widget 6: `MISSING_METRIC_MAPPING`
    - widget 7: `UNSUPPORTED_FORMULA`
    - widget 8: `MISSING_METRIC_MAPPING`×2
  - Every file under `tmp` except `source/` is byte-equal to `fixtures/expected/postgres-p0/`.
- [ ] **Step 2: Write `overview screenboard is blocked without artifact`.**
  - There are 10 widget items with code `UNSUPPORTED_WIDGET` (`Widget type 'group' is not supported.`).
  - There's no `dashboards/postgres-overview.json`.
- [ ] **Step 3: Generate the expected tree.**
  - Run `uv run migrator convert --source datadog --input fixtures/datadog/integrations-core/postgres/dashboards --mapping mappings/datadog/postgres.json --out /tmp/pg-p0`.
  - Review `dashboards/postgres-metrics.json` and `report.json` by hand against the assertions above.
  - Copy everything except `source/` into `fixtures/expected/postgres-p0/`.
- [ ] **Step 4: Verify.** Run `uv run migrator test`. It must PASS, and so must the determinism test from plan 01.
- [ ] **Step 5: Check against real data (read-only, manual).**
  - In the Dash0 UI or through the `dash0` MCP `promql` tool, on dataset `default`, run the widget-1 query.
  - Expect two series, `astronomy_db` and `postgres`, with small integer values (about 5 and 3 on 2026-11-07).
  - Record the result in `docs/STATUS.md` as `semantics: manual check`. Don't set `report.validation.semantics`.
- [ ] **Step 6: Document.** Update `README.md` with the golden command and its output, and mark plan 04 Done in `docs/handoff/README.md`.
- [ ] **Step 7: Commit.** `git add fixtures/expected tests README.md docs && git commit -m "test: golden Postgres dashboard conversion"`.
