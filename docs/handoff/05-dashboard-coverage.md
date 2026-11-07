# 05 — Dashboard coverage ladder: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise "Postgres - Metrics" from 1 to 6 of 9 translated widgets, and make "Postgres - Overview" convert partially. To get there, add: the `rate` mapping kind, fixed matchers, a documented default aggregator, unit scaling, series-grain collapsing, arithmetic formulas, template variables, more widget types and legends.

**Architecture:** Every feature extends the existing pieces from plans 02–04 (`MetricMapping` union, `compileMetricQuery`, `compileDashboard`). Each one is a reviewed rule with tests. There's still no general expression engine: formulas use a 4-operator grammar over query names and numbers.

**Tech Stack:** TypeScript, zod, vitest.

**Spec:** [00-context.md](00-context.md) §6, §7 and §8; the widget ladder in [DASH0_INVENTORY.md](../DASH0_INVENTORY.md#postgres-postgres---metrics-widget-ladder).

**Depends on:** plan 04. Tasks 6 and 7 also depend on plan 07 Task 1, the Dash0 contract check of plugin kinds, before their output can be called "renders in Dash0".

## Global Constraints

- **Freeze the plan 04 golden first** (Task 0). `fixtures/expected/postgres-p0/` must keep passing, using a frozen mapping copy.
- New mapping entries need a `ref` (the metrics_mapping row, or a doc URL) and `reviewed: null` until a human reviews them.
- The rendering shapes are exact:
  - rate: `rate(<selector>[$__rate_interval])`;
  - scale: `(<expr>) * <scale>`;
  - grain: `<agg> [by (g)] (<grainAgg> by (<g ∪ grain>) (<inner>))`.

## Review Focus

1. **Sum over series split by a collector restart:** with a `grain` set, there's no double counting. Covered by `grain collapses duplicate resource series` (Task 4).
2. **A formula combining queries with different group-by sets:** block it, because PromQL vector matching would silently drop series. Covered by `blocks formulas with mismatched grouping` (Task 5).
3. **A CPU widget where one of six series is unmappable** (`system.cpu.guest`): the whole widget stays blocked. Covered by `cpu widget stays blocked on guest` (Task 9).
4. **A rate mapping used on a metric whose Dash0 type is `gauge`:** reject the mapping file. Covered by `rate requires sum target` (Task 2).
5. **Scale combined with a group-by:** the multiplication wraps the whole aggregation, not the selector. Covered by `scale wraps aggregation` (Task 3).

---

### Task 0: Freeze the P0 golden

**Files:**
- Create: `fixtures/mappings/postgres-p0.json` (a byte copy of the current `mappings/datadog/postgres.json`)
- Modify: `tests/golden.test.ts`, so the P0 case uses the frozen copy

- [ ] Copy the file, point the P0 test at it, and run `npm test`. It must PASS.
- [ ] Commit: `test: freeze P0 golden mapping`.

### Task 1: Documented default aggregator

**Files:**
- Modify: `src/source/datadog/compile-query.ts`
- Test: `tests/datadog/compile-query.test.ts`

**Interfaces:**
- Produces: the exported constant `DEFAULT_SPACE_AGGREGATOR: SpaceAggregator`, with the doc URL in a comment.

- [ ] **Step 1: Look up Datadog's documented default.** Find the documented default space aggregation for metric queries without one (start at https://docs.datadoghq.com/metrics/#space-aggregation). Record the URL and the quote in the constant's comment.
  - If the docs don't state one, stop: keep `MISSING_AGGREGATOR`, skip this task, and note it in `docs/STATUS.md`.
- [ ] **Step 2: Write the failing test `applies the documented default aggregator`.**
  - `postgresql.connections{*}` gives `'<default> ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})'`.
  - Diagnostic codes are `["DEFAULT_AGGREGATOR_APPLIED"]`, with severity warning and message `No space aggregator; applied Datadog's documented default '<default>'.`
- [ ] **Step 3: Implement it.** Replace check 2 (`MISSING_AGGREGATOR`) with the warning. Then **Step 4:** run `npm test`; it must PASS. Commit.

### Task 2: The `rate` kind and fixed matchers

**Files:**
- Modify: `src/source/datadog/mapping.ts`, `src/source/datadog/compile-query.ts`, `mappings/datadog/postgres.json`
- Test: `tests/datadog/mapping.test.ts`, `tests/datadog/compile-query.test.ts`

**Interfaces:**
- Produces:
  - `RateMapping`: like `GaugeMapping`, but `kind: "rate"` and `target.type` must be `"sum"`.
  - A new optional field on both kinds: `matchers: Record<string, string>`. Fixed label matchers come after the source filters, sorted by label.
  - `MetricMapping = GaugeMapping | RateMapping`.

- [ ] **Step 1: Write the failing tests.**
  - `rate requires sum target`: `{kind: "rate", target: {type: "gauge"}}` gives `ok:false`.
  - `compiles rate`: `avg:postgresql.rows_fetched{$scope}` with `rows_fetched → {kind: "rate", target: {name: "postgresql.tup_fetched", type: "sum"}}` gives `'avg (rate({otel_metric_name="postgresql.tup_fetched", otel_metric_type="sum"}[$__rate_interval]))'`.
  - `appends fixed matchers`: `sum:system.net.bytes_rcvd{$scope}` with `matchers: {system_network_direction: "receive"}` gives `'sum (rate({otel_metric_name="system.network.io", otel_metric_type="sum", system_network_direction="receive"}[$__rate_interval]))'`.
- [ ] **Step 2: Implement it.**
- [ ] **Step 3: Add mapping entries** to `mappings/datadog/postgres.json`, all with `reviewed: null`:

| Datadog metric | kind | target | matchers |
|---|---|---|---|
| `postgresql.rows_{fetched,returned,inserted,updated,deleted}` | rate | `postgresql.tup_{same}` (sum) | — |
| `system.load.1`, `system.load.5`, `system.load.15` | gauge | `system.cpu.load_average.1m`, `.5m`, `.15m` (gauge) | — |
| `system.net.bytes_rcvd`, `system.net.bytes_sent` | rate | `system.network.io` (sum) | `system_network_direction`: `receive` / `transmit` |

- [ ] **Step 4: Verify.** Run `npm test`; it must PASS. Request a human review of the new entries. Commit.

### Task 3: Unit scale

**Files:**
- Modify: `src/source/datadog/compile-query.ts`, `mappings/datadog/postgres.json`
- Test: `tests/datadog/compile-query.test.ts`

- [ ] **Step 1: Write the failing tests.**
  - `scale wraps aggregation`: `max:system.cpu.iowait{$scope}` with `{kind: "gauge", target: {name: "system.cpu.utilization", type: "gauge"}, matchers: {cpu_mode: "wait"}, scale: 100}` gives `'(max ({otel_metric_name="system.cpu.utilization", otel_metric_type="gauge", cpu_mode="wait"})) * 100'`.
  - `rejects non-finite or non-positive scale`: `scale: 0` gives a mapping parse error.
- [ ] **Step 2: Implement it.** Remove check 4 for finite scales greater than 0.
- [ ] **Step 3: Add mapping entries** for `system.cpu.{idle,system,iowait,user,stolen}`. Each is a gauge on `system.cpu.utilization`, with `cpu_mode` set to `idle`, `system`, `wait`, `user` or `steal`, and scale 100.
  - Add **no** entry for `system.cpu.guest`.
- [ ] **Step 4: Verify.** Run `npm test`; it must PASS. Request a human review. Commit.

### Task 4: Series grain

This collapses target series to the Datadog series grain. It handles both resource-hash duplicates and per-CPU versus per-host differences.

**Files:**
- Modify: `mapping.ts`, `compile-query.ts`, `mappings/datadog/postgres.json`
- Test: `tests/datadog/compile-query.test.ts`

**Interfaces:**
- Produces: the optional mapping field `grain: { labels: string[]; aggregation: "avg" | "max" | "min" | "sum" }`.

- [ ] **Step 1: Write the failing tests.**
  - `grain collapses duplicate resource series`: the golden connections query, with `grain: {labels: ["service_instance_id"], aggregation: "max"}`, gives `'avg by (postgresql_database_name) (max by (postgresql_database_name, service_instance_id) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"}))'`.
  - `grain composes with rate and scale`:
    - Input: CPU user with `grain: {labels: ["host_name"], aggregation: "avg"}`.
    - Expected: `'(avg (avg by (host_name) ({…cpu_mode="user"}))) * 100'`, with the full selector written out in the test.
- [ ] **Step 2: Implement it.**
  - Group labels come first; then grain labels not already in the group, in mapping order.
  - With `rate`, the inner expression is the `rate(...)`.
- [ ] **Step 3: Set grains in the mapping.**
  - `postgresql.connections`: `{labels: ["service_instance_id"], aggregation: "max"}`.
  - The CPU entries: `{labels: ["host_name"], aggregation: "avg"}`.
- [ ] **Step 4: Verify.** Run `npm test`; it must PASS. Request a human review. Commit.

### Task 5: Arithmetic formulas

**Files:**
- Create: `src/source/datadog/formula.ts`
- Modify: `dashboard.ts`
- Test: `tests/datadog/formula.test.ts`

**Interfaces:**
- Produces:
  - `export type Formula = { kind: "num"; value: string } | { kind: "ref"; name: string } | { kind: "bin"; op: "+" | "-" | "*" | "/"; left: Formula; right: Formula }`
  - `export function parseFormula(text: string): { ok: true; formula: Formula } | { ok: false; offset: number }`. The grammar is `expr := term (("+"|"-") term)*`, `term := factor (("*"|"/") factor)*`, `factor := number | ident | "(" expr ")"`. It consumes the full input, and spaces are allowed between tokens.
  - `export function renderFormula(f: Formula, compiled: Record<string, { promql: string; groupLabels: string[] }>): { ok: true; promql: string; groupLabels: string[] } | { ok: false; reason: string }`. Each reference renders as `(<promql>)`. Every referenced query must have the same set of group labels.

- [ ] **Step 1: Write the failing tests.**
  - `parses precedence`: `query1 / (query1 + query2) * 100` gives the expected tree.
  - `renders subtraction`: `query2 - query1` with `{query1: {promql: "A", groupLabels: []}, query2: {promql: "B", groupLabels: []}}` gives `"(B) - (A)"`.
  - `blocks formulas with mismatched grouping`: `groupLabels` `["a"]` against `[]` gives `ok:false`, with reason `grouping mismatch`.
  - `rejects functions in formulas`: `top(query1, 5, 'mean', 'desc')` gives `ok:false` from `parseFormula`.
- [ ] **Step 2: Implement it.** In `compileDashboard`, replace the "formula must equal a query name" rule:
  - parse the formula, then compile every referenced query;
  - render the formula, or emit `UNSUPPORTED_FORMULA` with the reason.
- [ ] **Step 3: Verify.** Run `npm test`. The plan 04 synthetic test for `query1 * 100` now translates; update that expectation deliberately. Commit.

### Task 6: Template variables → Perses `ListVariable`

**Files:**
- Modify: `dashboard.ts`, `compile-query.ts`
- Test: `tests/datadog/dashboard.test.ts`

**Rule.**

- A variable with a non-null `prefix` whose prefix tag has a label mapping in **every** query that uses it becomes:
  `{kind: "ListVariable", spec: {name, display: {name}, allowAllValue: true, allowMultiple: true, defaultValue: "$__all", plugin: {kind: "PrometheusLabelValuesVariable", spec: {labelName: <label>}}}}`.
- The query then gets the matcher `<label>=~"$<name>"`.
- Variables with no prefix (`$scope`) stay dropped with a warning.

- [ ] **Step 1: Write the failing test `maps prefixed variables to ListVariable`.**
  - Input: a synthetic dashboard with `{name: "db", prefix: "db", default: "*"}` and query `avg:postgresql.connections{$db}`.
  - Expected: `spec.variables[0].spec.plugin.spec.labelName === "postgresql_database_name"`, and the query contains `postgresql_database_name=~"$db"`.
- [ ] **Step 2: Implement it.** Then **Step 3:** run `npm test`; it must PASS.
- [ ] **Step 4: Gate.** Until plan 07 Task 1 confirms that Dash0 renders `ListVariable`, record it in the report as an info `OPTION_IGNORED` note: "variable rendering unverified in Dash0". Commit.

### Task 7: More widget types

The types are `note`, `query_value` and `group`.

**Files:**
- Modify: `dashboard.ts`
- Test: `tests/datadog/dashboard.test.ts`

**Rules:**

- `note` → panel plugin `{kind: "Markdown", spec: {text: definition.content}}`, with no queries.
- `query_value` → `{kind: "StatChart", spec: {calculation: <c>}}`. Map Datadog `requests[0].queries[0].aggregator` → `c`: `avg → "mean"`, `last → "last-number"`, `max → "max"`, `min → "min"`, `sum → "sum"`. Any other value → `UNSUPPORTED_WIDGET`.
- `group` → its children become their own Grid layout, `{kind: "Grid", spec: {display: {title: group.title}, items: [...]}}`. Child panels use the key `widget-<i>-<j>`. Child source paths are `widgets[i].definition.widgets[j]`. The group itself isn't an item; its children are.

- [ ] **Step 1: Write the failing tests.**
  - `note becomes Markdown`.
  - `query_value maps aggregator to calculation`.
  - `group children become a titled grid`. The child key is `widget-0-1`.
- [ ] **Step 2: Implement it.** Then **Step 3:** run `npm test`; it must PASS. Group flattening changes the "Overview" item counts, so update any earlier test that asserts them.
- [ ] **Step 4: Gate.** The plugin kinds `Markdown` and `StatChart` must be confirmed by plan 07 Task 1 before they're marked "renders in Dash0" in `docs/STATUS.md`. Commit.

### Task 8: Legend names

- [ ] **Step 1: Write the failing test `group-by sets seriesNameFormat`.** The golden connections panel query gets `seriesNameFormat: "{{postgresql_database_name}}"`. With several labels, join them as `"{{a}} / {{b}}"`.
- [ ] **Step 2: Implement it** in `dashboard.ts`, from `CompiledQuery.groupLabels` (or from the formula's group labels). Then **Step 3:** run `npm test`; it must PASS. Commit.

### Task 9: Golden P1

**Files:**
- Create: `fixtures/expected/postgres-p1/`
- Test: `tests/golden.test.ts` (new case)

- [ ] **Step 1: Write the failing test `postgres p1 golden`**, using the current `mappings/datadog/postgres.json`.
  - Translated "Metrics" widgets: 0, 1, 2, 4, 6, 8.
    - If Task 1 was skipped because there's no documented default, widgets 2 and 4 stay blocked with `MISSING_AGGREGATOR`. Assert that instead.
  - Blocked: widget 3 (`MISSING_METRIC_MAPPING`, `system.io.util`), widget 5, and widget 7 (`MISSING_METRIC_MAPPING`, `system.mem.usable`).
  - Add `cpu widget stays blocked on guest`: widget 5's error is exactly one `MISSING_METRIC_MAPPING`, for `system.cpu.guest`.
  - "Overview" is `partial`. Record the exact translated and blocked counts after the first run, review them by hand, and write them into the test.
- [ ] **Step 2: Generate and review the expected tree, as in plan 04 Task 4.** Run `npm test`; it must PASS.
- [ ] **Step 3: Live read-only check** of the widget 0, 4, 6 and 8 queries in Dash0 (dataset `default`). Record the results in `docs/STATUS.md`. Commit.
