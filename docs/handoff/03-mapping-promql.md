# 03 — Mapping contract and PromQL compilation: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile a parsed `MetricQuery` into Dash0-compatible PromQL, using only a versioned mapping file that a human has reviewed. Every gap gets a precise diagnostic.

**Architecture:**

- `promql.py` (shared) renders selectors and escapes label values.
- `mapping.py` validates the Datadog mapping file with a strict pydantic model.
- `compile_query.py` applies a fixed sequence of checks, stops at the first blocking error for each query, collects warnings, and renders `agg [by (labels)] (selector)`.

**Tech Stack:** Python 3.13 (uv), pydantic, pytest.

**Spec:** [00-context.md](00-context.md) §2 (rules 3–4), §3 (A1), §7 (Dash0 PromQL conventions) and §8.

**Depends on:** plans 01 and 02.

## Global Constraints

- The selector shape is exactly `{otel_metric_name="<name>", otel_metric_type="<type>"[, <label>="<value>"]...}`, with `", "` separators and matchers in source filter order.
- The aggregation shape is exactly `<agg> (<selector>)` or `<agg> by (<l1>, <l2>) (<selector>)`.
- A mapped label name must match `^[a-zA-Z_][a-zA-Z0-9_]*$`. No dot → underscore conversion happens at runtime; the mapping file states the exact label.
- Only a human may set `reviewed`. Coding assistants leave it `null`.
- In this plan, `scale` must be `1` and `aggregator` must be present. Plan 05 relaxes both.

## Review Focus

1. **A tag value containing `"` or `\`:** escape it in the PromQL string. It must never break out of the selector. Covered by `escapes label values` (Task 1).
2. **A group-by tag with no label mapping:** block the query, not silently drop the grouping. Covered by `blocks unmapped group-by tag` (Task 3).
3. **A template variable whose default isn't `*`:** block, because dropping it would change what the chart shows. Covered by `blocks non-star template default` (Task 3).
4. **A mapping file with a label like `db.namespace`:** reject the file with exit 1, because Dash0 labels use underscores. Covered by `rejects dotted label names` (Task 2).
5. **A mapping entry that hasn't been reviewed:** compile it, but warn `UNREVIEWED_MAPPING` on every use. Covered by `warns on unreviewed entries` (Task 3).

---

### Task 1: Shared PromQL rendering

**Files:**
- Create: `src/migrator/promql.py`
- Test: `tests/test_promql.py`

**Interfaces:**
- Produces:
  - `export interface Matcher { label: string; value: string }`
  - `export function escapeLabelValue(value: string): string` escapes `\` → `\\`, `"` → `\"` and newline → `\n`, in a single pass.
  - `export function renderSelector(metric: { name: string; type: string }, matchers: Matcher[]): string`

- [ ] **Step 1: Write the failing tests.**

```ts
import { describe, expect, it } from "vitest";
import { escapeLabelValue, renderSelector } from "../src/promql.js";

describe("promql", () => {
  it("escapes label values", () => {
    expect(escapeLabelValue('a"b\\c\nd')).toBe('a\\"b\\\\c\\nd');
  });
  it("renders the Dash0 selector", () => {
    expect(renderSelector({ name: "postgresql.backends", type: "sum" }, [{ label: "postgresql_database_name", value: "astronomy_db" }]))
      .toBe('{otel_metric_name="postgresql.backends", otel_metric_type="sum", postgresql_database_name="astronomy_db"}');
  });
});
```

- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS.
- [ ] **Step 5: Commit.** `git add src/migrator/promql.py tests/test_promql.py && git commit -m "feat: PromQL selector rendering and escaping"`.

### Task 2: Mapping schema and loader

**Files:**
- Create: `src/migrator/source/datadog/mapping.py`
- Test: `tests/datadog/test_mapping.py`

**Interfaces:**
- Produces:

```ts
export interface Reviewed { by: string; date: string /* YYYY-MM-DD */; evidence: string }
export interface GaugeMapping { kind: "gauge"; target: { name: string; type: "gauge" | "sum" }; sourceUnit: string; targetUnit: string; scale: number; labels: Record<string, string>; ref: string; reviewed: Reviewed | null }
export type MetricMapping = GaugeMapping; // plan 05 adds RateMapping, plan 06 adds ExpressionMapping
export interface DatadogMapping { version: 1; source: "datadog"; metrics: Record<string, MetricMapping> }
export function parseMapping(raw: unknown): { ok: true; mapping: DatadogMapping } | { ok: false; errors: string[] };
```

- Use strict pydantic models (`extra="forbid"`, unknown keys rejected) and a discriminated union on `kind` (`Field(discriminator="kind")`).
- Each error message is `<json.path>: <pydantic message>`.
- `runConvert` (plan 01) calls `parseMapping` through the provider. `{ok:false}` becomes an `InputError("invalid mapping: " + errors.join("; "))`, which exits 1. Wire this in `datadogProvider.compile`, at its first line.

- [ ] **Step 1: Write the failing tests.**
  - `accepts a minimal gauge entry`, using the example in Task 4.
  - `rejects dotted label names`: `labels: {db: "db.namespace"}` gives `ok:false`, and the errors match `/metrics\.postgresql\.connections\.labels\.db/`.
  - `rejects unknown kind`: `kind: "histogram"` gives `ok:false`.
  - `rejects wrong source`: `source: "grafana"` gives `ok:false`.
  - `rejects unknown keys`: an extra key `foo` gives `ok:false`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: Datadog mapping schema"`.

### Task 3: compileMetricQuery

**Files:**
- Create: `src/migrator/source/datadog/compile_query.py`
- Test: `tests/datadog/test_compile_query.py`

**Interfaces:**
- Consumes: `MetricQuery` (plan 02), `DatadogMapping` (Task 2), `renderSelector` (Task 1), `Diagnostic` (plan 01).
- Produces:

```ts
export interface TemplateVariable { name: string; prefix: string | null; default: string | null }
export interface QueryContext { sourceId: string; sourcePath: string; sourceText: string; variables: TemplateVariable[] }
export type CompiledQuery =
  | { ok: true; promql: string; groupLabels: string[]; diagnostics: Diagnostic[] }
  | { ok: false; diagnostics: Diagnostic[] };
export function compileMetricQuery(q: MetricQuery, mapping: DatadogMapping, ctx: QueryContext): CompiledQuery;
```

**Check order.** The first blocking check that fails returns `ok:false`, with any warnings collected so far plus that error:

1. `functions.length > 0` → `UNSUPPORTED_QUERY_FUNCTION`: `Query function '.<name>()' is not supported.`
2. `aggregator === null` → `MISSING_AGGREGATOR`: `Query has no space aggregator.`
3. The metric isn't in `mapping.metrics` → `MISSING_METRIC_MAPPING`: `No mapping for metric '<m>'.`, with suggestedAction `Add a reviewed entry for '<m>' to the mapping file.`
4. `scale !== 1` → `UNSUPPORTED_UNIT_CONVERSION`.
5. `reviewed === null` → warning `UNREVIEWED_MAPPING`. Continue.
6. Filters, in order:
   - A variable that isn't in `ctx.variables` → `UNSUPPORTED_TEMPLATE_VARIABLE`.
   - A variable whose default is `null` or `"*"` → warning `TEMPLATE_VARIABLE_DROPPED`, `Template variable '$<n>' (default '*') dropped; the converted panel shows all series.` Continue.
   - Any other variable default → `UNSUPPORTED_TEMPLATE_VARIABLE`.
   - A tag key that isn't in `labels` → `MISSING_LABEL_MAPPING`.
7. Group-by tags: a tag that isn't in `labels` → `MISSING_LABEL_MAPPING`.

Every diagnostic carries `ctx.sourceId`, `ctx.sourcePath` and `sourceText: ctx.sourceText`. Severity is `error` for blocking checks and `warning` otherwise.

- [ ] **Step 1: Write the failing tests.** All use an inline mapping with `postgresql.connections` → `{kind:"gauge", target:{name:"postgresql.backends", type:"sum"}, scale:1, labels:{db:"postgresql_database_name", host:"host_name"}, reviewed:{by:"t", date:"2026-11-07", evidence:"test"}, …}`, and `variables: [{name:"scope", prefix:null, default:"*"}]`.
  - `compiles the golden connections query`:
    - Input: `parseMetricQuery("avg:postgresql.connections{$scope} by {db}")`.
    - Expected `promql`: `'avg by (postgresql_database_name) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})'`, with `groupLabels: ["postgresql_database_name"]`.
    - Expected diagnostics: codes `["TEMPLATE_VARIABLE_DROPPED"]`.
  - `compiles tag filters into matchers`: `max:postgresql.connections{db:astronomy_db}` gives `'max ({otel_metric_name="postgresql.backends", otel_metric_type="sum", postgresql_database_name="astronomy_db"})'`.
  - `blocks rollup`: `avg:postgresql.connections{*}.rollup(max)` gives `ok:false`, codes `["UNSUPPORTED_QUERY_FUNCTION"]`.
  - `blocks missing aggregator`: `postgresql.connections{*}` gives codes `["MISSING_AGGREGATOR"]`.
  - `blocks unmapped metric`: `avg:system.io.util{$scope}` gives codes `["MISSING_METRIC_MAPPING"]`.
  - `blocks unmapped group-by tag`: `avg:postgresql.connections{*} by {table}` gives codes `["MISSING_LABEL_MAPPING"]`.
  - `blocks non-star template default`: variables `[{name:"scope", prefix:null, default:"env:prod"}]` gives codes `["UNSUPPORTED_TEMPLATE_VARIABLE"]`.
  - `blocks scale other than 1`: an entry with `scale: 100` gives codes `["UNSUPPORTED_UNIT_CONVERSION"]`.
  - `warns on unreviewed entries`: with `reviewed: null`, the result is `ok:true` and the codes include `"UNREVIEWED_MAPPING"`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: compile Datadog metric queries to Dash0 PromQL"`.

### Task 4: Postgres golden mapping file

**Files:**
- Create: `mappings/datadog/postgres.json`
- Test: `tests/datadog/test_mapping_files.py`

**Interfaces:**
- Produces: the mapping file that plan 04's golden run uses.

- [ ] **Step 1: Write the file.**

```json
{
  "version": 1,
  "source": "datadog",
  "metrics": {
    "postgresql.connections": {
      "kind": "gauge",
      "target": { "name": "postgresql.backends", "type": "sum" },
      "sourceUnit": "connection",
      "targetUnit": "1",
      "scale": 1,
      "labels": { "db": "postgresql_database_name", "host": "host_name" },
      "ref": "https://docs.datadoghq.com/opentelemetry/guide/metrics_mapping/ (postgresql.connections <-> postgresql.backends); labels from docs/DASH0_INVENTORY.md",
      "reviewed": null
    }
  }
}
```

- [ ] **Step 2: Write the test.** `every mapping file under mappings/datadog parses`: glob the directory, and `parseMapping` must return `ok:true` for each file.
- [ ] **Step 3: Verify.** Run `uv run migrator test tests/datadog`. It must PASS.
- [ ] **Step 4: Request a human review.**
  - Ask the user or a teammate to check the entry against the metrics_mapping row and `docs/DASH0_INVENTORY.md`, and then set `reviewed` themselves.
  - Record the semantic note: `backends` counts all backend types; Datadog's `connections` counts `numbackends`.
  - **Don't fill in `reviewed` yourself.**
- [ ] **Step 5: Commit.** `git add mappings tests && git commit -m "feat: Postgres golden mapping (pending human review)"`.
