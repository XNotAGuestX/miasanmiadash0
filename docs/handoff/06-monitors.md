# 06 — Datadog metric monitors → Prometheus rules and Dash0 check rules: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the golden monitor `percent_usage_connections` into two artifacts rendered from one condition: a Prometheus rule group (warning + critical) and a disabled Dash0 check rule (`degraded` / `failed`). Block `replication_delay` with a precise reason. This work is secondary to the dashboard converter (decision D6).

**Architecture:**

- `monitor.ts` parses the monitor query, reusing `parseMetricQuery` for the inner metric query, and evaluates options against a reviewed allowlist (decision A3).
- It compiles the inner query with `compileMetricQuery`. A new `expression` mapping kind provides derived ratios.
- It wraps the result as `<time>_over_time((<space-aggregated>)[<window>:1m])`.
- Both outputs come from the same condition string.

**Tech Stack:** TypeScript, zod, vitest.

**Spec:** [00-context.md](00-context.md) §3 (A2, A3), §6 (monitor facts), §7 (check-rule body) and §8.

**Depends on:** plans 01–03 (04 only for shared writers).

## Global Constraints

- The rolling window stays in the expression: `last_15m` becomes the subquery `[15m:1m]`. **It never becomes `for: 15m`.**
- Time aggregator mapping: `avg → avg_over_time`, `max → max_over_time`, `min → min_over_time`, `sum → sum_over_time`. The subquery step is the check interval, `1m`.
- Check rule:
  - `interval: "1m"`, `for: "0s"`, `enabled: false`, `labels: {}`;
  - `thresholds: {failed: critical, degraded: warning}`, where `degraded` is present only if there's a warning;
  - the expression ends with ` <cmp> $__threshold`;
  - no `id`.
- Prometheus rule group: one group, `name: <slug>`, `interval: "1m"`. Each rule has `alert: <slug>`, `labels: {severity: "warning"|"critical"}`, and annotations `{summary, description}`. The warning rule comes first.
- Escape Go-template braces in annotations in **one pass**: `{{` → `{{ "{{" }}` and `}}` → `{{ "}}" }}`.
- Text limits: summary ≤ 255 and description ≤ 2048 characters, measured after escaping. Cut only between escape tokens, append `…`, and emit `TEXT_TRUNCATED`.

## Review Focus

1. **Datadog templates in names and messages** (`{{host.name}}`, `{{#is_alert}}`): escape them, so the Prometheus and Dash0 annotation renderers never execute them. Covered by `escapes template braces in one pass` (Task 4).
2. **The inline threshold disagrees with `options.thresholds.critical`:** block the monitor. Covered by `blocks threshold mismatch` (Task 4).
3. **A warning threshold on the wrong side** of critical for the comparator: block it. Covered by `blocks inverted warning` (Task 4).
4. **Non-default no-data handling** (`notify_no_data: true`): block it, because Dash0 behaves differently on missing data. Covered by `blocks non-default no-data` (Task 2).
5. **A window over 7 days** (`last_2w` isn't in the grammar; `last_8d` is): block it, as over Dash0's limit. Covered by `blocks windows over 7d` (Task 4).

---

### Task 1: Monitor query parser

**Files:**
- Create: `src/source/datadog/monitor.ts` (parser part)
- Modify: `src/source/datadog/model.ts`
- Test: `tests/datadog/monitor-parse.test.ts`

**Interfaces:**
- Produces:

```ts
export type TimeAggregator = "avg" | "max" | "min" | "sum";
export type Comparator = ">" | ">=" | "<" | "<=";
export interface MonitorQuery { timeAggregator: TimeAggregator; window: { amount: number; unit: "m" | "h" | "d" }; query: MetricQuery; comparator: Comparator; threshold: number }
export function parseMonitorQuery(text: string):
  | { ok: true; monitor: MonitorQuery }
  | { ok: false; code: "UNSUPPORTED_QUERY_SYNTAX" | "UNSUPPORTED_QUERY_FUNCTION"; offset: number; message: string };
```

**Rules:**

- The prefix must match `^(avg|max|min|sum)\(last_(\d+)(m|h|d)\):`.
- The suffix must match ` (>=|<=|>|<) (-?\d+(\.\d+)?)$`.
- The middle goes to `parseMetricQuery`. Its error offsets are shifted by the prefix length.

- [ ] **Step 1: Write the failing tests.**
  - `parses the golden monitor`: `avg(last_15m):avg:postgresql.percent_usage_connections{*} > 0.9` gives `{timeAggregator: "avg", window: {amount: 15, unit: "m"}, comparator: ">", threshold: 0.9, query: {aggregator: "avg", metric: "postgresql.percent_usage_connections", filters: [], groupBy: [], functions: []}}`.
  - `blocks anomalies`: the pinned `replication_delay` query gives `code: "UNSUPPORTED_QUERY_FUNCTION"` and the message `Function 'anomalies' is not supported.`
  - `blocks arithmetic`: `avg(last_5m):100 * avg:redis.mem.used{*} / avg:redis.mem.maxmemory{*} > 90` gives `UNSUPPORTED_QUERY_SYNTAX`.
  - `blocks unknown window unit`: `avg(last_1w):avg:x{*} > 1` gives `UNSUPPORTED_QUERY_SYNTAX` at offset 0.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 2: Options allowlist

**Files:**
- Modify: `src/source/datadog/monitor.ts`
- Test: `tests/datadog/monitor-options.test.ts`

**Interfaces:**
- Produces: `export function evaluateMonitorOptions(options: Record<string, unknown>, ctx: { sourceId: string }): { ok: true; thresholds: { critical: number; warning?: number }; diagnostics: Diagnostic[] } | { ok: false; diagnostics: Diagnostic[] }`

**Reviewed allowlist.** Source paths are `options.<key>`.

| Key | Accepted silently | Accepted with `MONITOR_OPTION_APPROXIMATED` warning | Otherwise |
|---|---|---|---|
| `thresholds` | object with finite `critical`, optional finite `warning` | — | other keys such as `critical_recovery`, `warning_recovery`, `ok` or `unknown` → `UNSUPPORTED_MONITOR_OPTION` |
| `require_full_window` | `false` | `true`: "Dash0 evaluates partial windows." | — |
| `new_host_delay` | `null`, `0` | `> 0`: "No new-host grace period in Dash0." | — |
| `notify_no_data` | `false` | — | blocked |
| `no_data_timeframe` | `null` | — | blocked |
| `timeout_h` | `0`, `null` | — | blocked |
| `renotify_interval` | `0`, `"0"`, `null` | — | blocked |
| `escalation_message` | `""` | — | blocked |
| `notify_audit`, `locked` | `false` | — | blocked |
| `include_tags` | `true`, `false` (info `OPTION_IGNORED`) | — | — |
| any other key | — | — | `UNSUPPORTED_MONITOR_OPTION` |

- [ ] **Step 1: Write the failing tests.**
  - `golden options pass with approximations`: the pinned `percent_usage_connections` options give `thresholds {critical: 0.9, warning: 0.8}`, and warning codes `["MONITOR_OPTION_APPROXIMATED", "MONITOR_OPTION_APPROXIMATED"]` at paths `options.new_host_delay` and `options.require_full_window`, sorted by path.
  - `blocks non-default no-data`: `notify_no_data: true` gives `ok:false` and `UNSUPPORTED_MONITOR_OPTION`.
  - `blocks recovery thresholds`: `thresholds.critical_recovery` gives `ok:false`.
  - `blocks unknown keys`: `threshold_windows` gives `ok:false`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 3: The `expression` mapping kind and the Postgres ratio

**Files:**
- Modify: `src/source/datadog/mapping.ts`, `compile-query.ts`, `mappings/datadog/postgres.json`
- Test: `tests/datadog/compile-query.test.ts`

**Interfaces:**
- Produces: `ExpressionMapping { kind: "expression"; expression: string; outputLabels: string[]; labels: Record<string, string>; sourceUnit: string; targetUnit: string; scale: number; ref: string; reviewed: Reviewed | null }`. It's added to the `MetricMapping` union.

**Rendering:**

- Build the matcher string from the filters: `, <label>="<escaped>"` for each, in source order, or `""` when there are none.
- Replace **every** literal `$filters` in `expression` with that string, in one pass.
- Render `<agg> [by (<labels>)] (<expression>)`.
- Each group-by label must be in `outputLabels`; otherwise emit `MISSING_LABEL_MAPPING`.

- [ ] **Step 1: Write the failing test `compiles expression mappings`.** With the entry below, `avg:postgresql.percent_usage_connections{*}` gives:

  `'avg (sum by (service_instance_id) (max by (service_instance_id, postgresql_database_name) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})) / on (service_instance_id) max by (service_instance_id) ({otel_metric_name="postgresql.connection.max", otel_metric_type="gauge"}))'`

- [ ] **Step 2: Implement it.**
- [ ] **Step 3: Add the entry** to `mappings/datadog/postgres.json`, with `reviewed: null`:

```json
"postgresql.percent_usage_connections": {
  "kind": "expression",
  "expression": "sum by (service_instance_id) (max by (service_instance_id, postgresql_database_name) ({otel_metric_name=\"postgresql.backends\", otel_metric_type=\"sum\"$filters})) / on (service_instance_id) max by (service_instance_id) ({otel_metric_name=\"postgresql.connection.max\", otel_metric_type=\"gauge\"$filters})",
  "outputLabels": ["service_instance_id"],
  "labels": { "host": "host_name" },
  "sourceUnit": "fraction", "targetUnit": "1", "scale": 1,
  "ref": "Derived: Datadog postgresql.percent_usage_connections = connections / max_connections (no 1:1 OTel metric). Dedup per docs/DASH0_INVENTORY.md#caveats",
  "reviewed": null
}
```

- [ ] **Step 4: Verify against real data (read-only).**
  - In Dash0 (dataset `default`), confirm `postgresql.connection.max` carries `service_instance_id`.
  - Then run the ratio at a 1m step. Expect about `0.08`.
  - If the label is missing, change the expression to divide by `scalar(max(...))`, update the test, and record why in `ref`.
- [ ] **Step 5: Request a human review.** Run `npm test`; it must PASS. Commit.

### Task 4: compileMonitor and both renderers

**Files:**
- Modify: `src/source/datadog/monitor.ts`
- Test: `tests/datadog/monitor.test.ts`

**Interfaces:**
- Produces:
  - `export interface MonitorCompilation { rule: RuleArtifact | null; item: ItemResult; diagnostics: Diagnostic[] }`
  - `export function compileMonitor(asset: SourceAsset, slug: string, mapping: DatadogMapping): MonitorCompilation`
  - `export function escapeTemplateBraces(text: string): string`

**Check order:**

1. `type` is `"query alert"` or `"metric alert"`, else `UNSUPPORTED_MONITOR_TYPE`.
2. `parseMonitorQuery`.
3. `evaluateMonitorOptions`.
4. `threshold === thresholds.critical`, else `THRESHOLD_MISMATCH`.
5. The warning is on the correct side: below critical for `>`/`>=`, above it for `<`/`<=`. Otherwise `THRESHOLD_MISMATCH`.
6. The window is ≤ 7d, else `UNSUPPORTED_MONITOR_OPTION`.
7. `compileMetricQuery` on the inner query, with `sourcePath: "query"`.
8. `@handle` tokens in `message` give a warning, `NOTIFICATION_NOT_MIGRATED`.
9. `priority` and `tags` give an info, `OPTION_IGNORED`.

- [ ] **Step 1: Write the failing tests.**
  - `golden monitor renders both artifacts`, using the pinned monitor, `mappings/datadog/postgres.json` and slug `postgres-number-of-connections-is-approaching-connection-limit-o`. That's `slugify(name)`, cut at 64 characters.
    - `checkRule.expression` is `avg_over_time((<the Task 3 expected PromQL>)[15m:1m]) > $__threshold`.
    - `checkRule.thresholds` is `{degraded: 0.8, failed: 0.9}`, and `enabled` is `false`.
    - The Prometheus `expr`s are `[<C> > 0.8, <C> > 0.9]`, with severities `["warning", "critical"]`.
  - `escapes template braces in one pass`: `escapeTemplateBraces("a {{host.name}} b")` is `'a {{ "{{" }}host.name{{ "}}" }} b'`.
  - `blocks threshold mismatch`: inline `> 0.95`, critical `0.9`.
  - `blocks inverted warning`: `>` with warning `0.95`, critical `0.9`.
  - `blocks windows over 7d`: `avg(last_8d)…`.
  - `truncates long descriptions`: a 3000-character message gives a description of ≤ 2048 characters ending in `…`, plus a `TEXT_TRUNCATED` warning.
  - `replication_delay is blocked`: `rule === null`, the item is `blocked`, and the codes are `["UNSUPPORTED_QUERY_FUNCTION"]`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 5: Wiring, validation and golden

**Files:**
- Modify: `src/source/datadog/index.ts`, `src/convert.ts`, `src/validation.ts`
- Create: `fixtures/expected/postgres-monitors/`
- Test: `tests/golden.test.ts` (new case)

**Interfaces:**
- Produces:
  - Files `rules/<slug>.prometheus.json|yaml` and `check-rules/<slug>.json`.
  - Manifest kinds `prometheus-rule` and `check-rule`, with `eligible` only if the monitor is `translated`.
  - `validateCheckRule(r: unknown): string[]`, a strict Zod schema of `Dash0CheckRule`.
  - PromQL syntax checking of every rule expression, through `checkPromqlSyntax`.

- [ ] **Step 1: Write the failing test `postgres monitors golden`.**
  - Input: `fixtures/datadog/integrations-core/postgres/monitors` with `mappings/datadog/postgres.json`.
  - Expect exit `2`: one translated monitor and one blocked.
  - Every file except `source/` is byte-equal to `fixtures/expected/postgres-monitors/`.
- [ ] **Step 2: Implement the wiring.** Generate and review the expected tree by hand, as in plan 04 Task 4. Run `npm test && npm run typecheck`; both must pass.
- [ ] **Step 3: Document.** Update `README.md`, and mark plan 06 Done in `docs/handoff/README.md`. Commit.
