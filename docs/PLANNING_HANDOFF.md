# Planning handoff: Datadog → Perses/Dash0 migrator (2026-11-07)

Written for the next planning session from the approved planning session of 2026-11-07. It describes planned behavior; nothing below is implemented unless stated.

## 1. Purpose and read order

This document hands planning to a new session. The next session must:

1. Inventory the default Dash0 dataset (read-only).
2. Order the services by the data it finds.
3. Get the three open decisions (§7) answered by the user.
4. Finalize the development plan (§9).

Read first: `AGENTS.md`, `docs/PROJECT_HANDOFF.md`, `docs/STATUS.md`, `docs/EXECUTION_PLAN.md`, all on branch `worktree-provider-interface-docs`.

**The highest-priority rule still holds.** Conversion is deterministic, and no LLM takes part in any source-to-Perses, query or alert translation step. Coding assistants write code, tests and *reviewed* mapping tables, but never translate migration inputs at runtime. Every mapping entry must be reviewed by a human before it counts as reviewed.

## 2. User goals and decisions, in order

| # | User statement / decision | Status |
|---|---|---|
| 1 | Hackathon goal: convert Datadog dashboard and alert definitions into open-source Perses definitions, working with Dash0. Dashboards and alerts come first. | Matches the handoff |
| 2 | Build iteratively: golden case first, then edge cases. | Matches the handoff |
| 3 | Keep it extensible with a source-provider adapter. Datadog comes first, but keep it open. If staying provider-agnostic would limit functionality, discuss it with the user, because primary functionality comes first. | Done, see #4 |
| 4 | **Translation need not be source-agnostic.** Only ensure an interface for choosing between providers exists. | **Done**: `SourceProvider` interface + static table, `--source datadog`. Commit `22dc712`, pushed, not merged |
| 5 | Datadog examples come from https://github.com/DataDog/integrations-core. **Postgres is the first example.** | Researched (§5.1) |
| 6 | Inputs can be **file or folder paths**. | Planned (§9 M1). The docs still say folder input is P1; update them |
| 7 | Output is **JSON, YAML, or direct publish** to an authenticated Dash0 user. | Planned. The docs still say YAML is P2; update them |
| 8 | The target ("our side") telemetry fields come from https://opentelemetry.io/docs/specs/semconv/db/postgresql/ | Researched: there's a gap (§5.2), decision open (§7.1) |
| 9 | **If not stated otherwise, output is in Perses format.** | Planned. Perses has no alert format (§7.2) |
| 10 | **Order the development plan and services by the example data that exists in the default Dash0 environment.** | **Blocked**: no data access (§4) |
| 11 | Wanted: a short list of what's missing for Postgres and other services. | §8 |
| — | Working preference: clarify with free-text questions; the user twice rejected multiple-choice prompts. | Note for the next session |

## 3. Repository state

- Path: `/Users/felix/tum/artemis/thinchackdash`. Remote: `git@github.com:XNotAGuestX/thinchackdash.git`.
- `main` holds `5cdffed init`: the initial docs (`AGENTS.md`, `CLAUDE.md`, `README.md`, `.env.example`, `.gitignore`, `docs/*`). It's pushed.
- Branch `worktree-provider-interface-docs` holds `22dc712 docs: add SourceProvider interface…`. It's pushed, not merged, and the worktree is at `.claude/worktrees/provider-interface-docs`. To merge: `git merge worktree-provider-interface-docs`.
- **No code exists yet**: no package, CLI, fixtures or tests.
- Unresolved: the challenge requires a fork of `vimouzin/dash0-dashboard-migrator` and a PR against its `main`. The current remote isn't that fork (see `docs/EXECUTION_PLAN.md` §0).

## 4. Access state and blockers

| Access | State |
|---|---|
| Dash0 MCP server | Configured at user scope: `dash0` → `https://api.eu-west-1.aws.dash0.com/mcp` (HTTP). `claude mcp list` shows **✔ Connected** after OAuth sign-in. **Its tools never loaded into this session**, even after `/exit` and resume, probably because the server was added after the session was created. **A brand-new session should load them.** Check with ToolSearch `dash0`. |
| Dash0 API token | None. No `.env`; no `DASH0_*` environment variables. |
| Dash0 CLI (`dash0`) | Not installed. Available via Homebrew tap `dash0hq/homebrew-dash0-cli`, v1.20.0. |
| Datadog API | No credentials (`DD_API_KEY`/`DD_APP_KEY` unset). Not needed for offline work with integrations-core assets. |
| GitHub reads | `gh api` works for public repos (integrations-core, semconv, collector-contrib, perses, dash0hq). |
| Headless `claude -p` | Fails with `Invalid API key · Fix external API key`. Don't rely on it. |

Region: the MCP URL implies the Dash0 organization is in **EU (eu-west-1)**. The API base is `https://api.eu-west-1.aws.dash0.com`.

## 5. Verified research (2026-11-07)

### 5.1 integrations-core `postgres/assets`

The folder contains `configuration/`, `dashboards/`, `dataflows.yaml`, `logs/`, `monitors/`, `saved_views/` and `service_checks.json`.

- **`dashboards/postgresql_dashboard.json`, "Postgres - Metrics"** (14.8 KB): `layout_type: ordered`, one template variable `scope` (prefix null, default `*`), and **9 timeseries widgets**. Requests use `{response_format: timeseries, queries[{data_source: metrics, name: queryN, query}], formulas[{formula: queryN}]}`.
  - The widgets are: rows fetched/returned/inserted/updated (4 requests); **Connections**, `avg:postgresql.connections{$scope} by {db}`; inserts/updates/deletes (3 queries, no aggregator); disk utilization, `avg:system.io.util{$scope}`; system load 1/5/15; CPU (6 `system.cpu.*` queries); I/O wait, `max:system.cpu.iowait{$scope}`; system memory (`sum:system.mem.*`); network (`sum:system.net.bytes_*`).
- **`dashboards/postgresql_screenboard_dashboard.json`, "Postgres - Overview"** (51.8 KB): ordered layout and variables `scope, table, db, host`.
  - Widget types: group×10, timeseries×13, toplist×8, query_table×3, note×3, query_value×2, log_stream×1.
  - Queries use `by {db|table|index|function|host|lock_mode,table}`, `.rollup(max)` and `.as_count()`.
  - Formulas: `query1 * 100`, `query1 / (query1 + query2) * 100`, `top(query1, 5, 'mean', 'desc')`, `week_before(query1)`, `count_nonzero(query1)`.
  - There's a log query: `source:postgresql (host:$host.value OR hostname:$host.value)`.
- **`monitors/percent_usage_connections.json`, the golden monitor:**
  - `query`: `avg(last_15m):avg:postgresql.percent_usage_connections{*} > 0.9`
  - `thresholds`: `{critical: 0.9, warning: 0.8}`
  - Other options: `require_full_window: true`, `new_host_delay: 300`, `notify_no_data: false`, `renotify_interval: "0"`, `include_tags: true`, `timeout_h: 0`
  - The message and name use `{{#is_alert}}…{{/is_alert}}` and `{{host.name}}`.
- **`monitors/replication_delay.json`, the blocked example:** `avg(last_1h):anomalies(avg:postgresql.replication_delay{*}, 'basic', 2, direction='above', alert_window='last_15m', interval=20, count_default_zero='true') >= 1`. It also has `threshold_windows` and `critical_recovery`. There's no deterministic equivalent, so it stays blocked.
- **Wrapper format:** integrations-core monitors are wrapped as `{version, created_at, last_updated_at, title, tags, description, definition: {…monitor API shape…}}`. The provider must unwrap `definition`; the API (`GET /api/v1/monitor/{id}`) returns the inner shape.
- Pin fixtures to an integrations-core commit SHA and include its license notice (check it; expected BSD-3-Clause).

### 5.2 OTel semantic conventions and PostgreSQL

- **semconv `db/postgresql`** covers **client** operations only: spans with `db.system.name=postgresql`, `db.namespace` (`{database}|{schema}`), `db.collection.name`, `db.operation.name`, `db.query.summary`, `db.query.text`, `db.response.status_code`, `server.address` and `server.port`.
  - Client metrics come from `database-metrics.md`: `db.client.operation.duration` and the connection-pool metrics `db.client.connection.count{db.client.connection.state=idle|used, db.client.connection.pool.name}`, `.max`, `.idle.max`, `.idle.min`, `.pending_requests`, `.timeouts`, `.create_time`, `.wait_time`, `.use_time`.
  - `model/postgresql/` contains only `spans.yaml`, so **semconv defines no PostgreSQL server metrics**.
- **The Datadog Postgres assets measure the server** (`pg_stat_*`). Client pool metrics **don't mean the same thing** (an application's pool versus server backends and `max_connections`). Mapping one to the other would break the "no inferred equivalence" rule.
- **OTel Collector `postgresqlreceiver`** (collector-contrib, latest release **v0.165.0**) defines the server metrics, and it already uses **semconv attribute names** (`db.namespace`, `db.collection.name`, `server.address`, `server.port`; resource attributes also include `postgresql.database.name`, `postgresql.table.name`, `postgresql.index.name`, `postgresql.schema.name`, `service.instance.id`). The relevant metrics are below; anything not marked "off" is enabled by default.

  | Metric | Type | Attributes |
  |---|---|---|
  | `postgresql.backends` | sum, non-monotonic | `db.namespace` |
  | `postgresql.connection.max` | gauge | none |
  | `postgresql.operations` | sum, monotonic | `operation`=ins/upd/del/hot_upd, `db.namespace`, `db.collection.name` |
  | `postgresql.rows` | sum, non-monotonic | `state`=dead/live, `db.namespace`, `db.collection.name` |
  | `postgresql.commits`, `postgresql.rollbacks` | sum, monotonic | `db.namespace` |
  | `postgresql.blocks_read` | sum, monotonic | `source`, `db.namespace`, `db.collection.name` |
  | `postgresql.db_size` | sum, non-monotonic, `By` | `db.namespace` |
  | `postgresql.table.size` | sum, non-monotonic, `By` | `db.namespace`, `db.collection.name` |
  | `postgresql.table.count` | sum, non-monotonic | `db.namespace` |
  | `postgresql.table.vacuum.count` | sum, monotonic | `db.namespace`, `db.collection.name` |
  | `postgresql.index.scans` | sum, monotonic | `db.namespace`, `db.collection.name`, `postgresql.index.name` |
  | `postgresql.index.size` | gauge | `db.namespace`, `db.collection.name`, `postgresql.index.name` |
  | `postgresql.bgwriter.{buffers.allocated, buffers.writes, checkpoint.count, duration, maxwritten}` | sums | — |
  | `postgresql.database.count` | sum, non-monotonic | — |
  | `postgresql.replication.data_delay` | gauge, `By` | `replication_client` |
  | `postgresql.wal.age` | gauge, `s` | — |
  | `postgresql.wal.lag` | gauge, `s` | `operation`, `replication_client` |
  | Off by default: `postgresql.deadlocks`, `postgresql.sequential_scans`, `postgresql.tup_{fetched,returned,inserted,updated,deleted}`, `postgresql.blks_{hit,read}`, `postgresql.temp_files`, `postgresql.temp.io`, `postgresql.database.locks`, `postgresql.function.calls`, `postgresql.query.*`, `postgresql.wal.delay` | | |

- **Datadog publishes the Datadog ↔ OTel metric mapping**: https://docs.datadoghq.com/opentelemetry/guide/metrics_mapping.md
  - Columns: `otel | datadog | description | filter | transform | Integration`. About 3,900 rows covering postgres, mysql, redis, kafka, hostmetrics, kubeletstats, docker, jvm and more.
  - Examples: `postgresql.connections` ↔ `postgresql.backends`; `postgresql.rows_hot_updated` ↔ `postgresql.operations` with filter `operation: hot_upd`.
  - Use it as the cited source for reviewed mapping entries. Still check each pair's meaning and units.
- `postgresql.percent_usage_connections` has **no 1:1 OTel metric**. It needs a reviewed derived expression, e.g. `sum by (server_address, server_port) (backends) / max by (…) (connection.max)`. Check the grouping labels against real data.

### 5.3 Dash0 (OpenAPI `https://www.dash0.com/docs/api-reference/openapi.json`, plus docs)

- **Auth:** `Authorization: Bearer <token>`. Static tokens start with `auth_`. Dataset: the `?dataset=` param wins over the `Dash0-Dataset` header; otherwise `default`.
- **PromQL naming:**
  - Select with `{otel_metric_name="postgresql.backends", otel_metric_type="sum"}`. `otel_metric_type` is one of `sum`, `gauge`, `histogram`, `exponential_histogram`, `summary`; `otel_metric_unit` also exists.
  - Bare dotted names fail.
  - Attribute dots become `_` (`db.namespace` → `db_namespace`). Resource and data-point attributes are both flat labels.
  - Every query must name a metric.
  - `rate(...[$__rate_interval])` works on sums; use `$__interval` for other aggregations.
  - Prometheus-style names also work (dots → `_`, `_total` added for counters, unit suffixes).
- **Read-only inventory endpoints:**
  - `GET /api/datasets`
  - `GET /api/prometheus/api/v1/labels`
  - `GET /api/prometheus/api/v1/label/{name}/values` (e.g. `otel_metric_name`, `service_name`, `otel_metric_type`)
  - `GET /api/prometheus/api/v1/series?match[]=…`
  - `GET|POST /api/prometheus/api/v1/query`, `/query_range`, `/format_query`, `/metadata`
  - `GET /api/dashboards`, `GET /api/dashboards/{originOrId}`
  - `GET /api/alerting/check-rules`, `GET /api/alerting/check-rules/{originOrId}`
  - `POST /api/topology` (service map); `POST /api/sql`
- **Dashboards:**
  - Use `POST /api/import/dashboard`, which is meant for one-time migrations and keeps the dashboard editable. `POST`/`PUT /api/dashboards` also exist; `PUT` is an upsert by origin.
  - Body: `{kind: "Dashboard", metadata: {name, …}, spec: <Perses spec>}`. `metadata.dash0Extensions.id` overwrites an existing dashboard, so omit it for create-only. Limit: 256 KB.
  - Seen in dash0hq fixtures:
    - panels `TimeSeriesChart`, `StatChart`, `PieChart`, `Dash0TreeMapChart`
    - query `TimeSeriesQuery` → `PrometheusTimeSeriesQuery{query, seriesNameFormat, minStep}`
    - layout `Grid` with 24 columns
    - no datasource needed
    - variable `Dash0FilterVariable{name, attributeKey, operator: is|is_any|is_not_set, values}`, used as `{otel_metric_name="…", $var}`
    - also `ListVariable`+`PrometheusLabelValuesVariable`, `StaticListVariable`, `TextVariable`
- **Check rules:**
  - Use `POST /api/import/check-rule` (or `/api/alerting/check-rules`, or `/bulk` with up to 1000 rules, atomic).
  - Required: `name`, `expression`.
  - Optional: `id` (origin/upsert key, unique per organization), `thresholds{degraded, failed}` (**critical is called `failed`**), `$__threshold` in the expression, `interval` (default 1m), `for` (default 0s, ≥ interval if set), `keep_firing_for`, `labels`, `annotations{summary ≤255, description ≤2048}`, `enabled`.
  - Limits: window ≤ 7d; the minimum interval grows with the window (≤1h10m → 1m).
  - **Prometheus rules are accepted**, via the `PrometheusRule` CRD, `dash0 apply`, or Terraform. Annotations `dash0-threshold-degraded`, `dash0-threshold-critical` and `dash0-enabled` are interpreted.
- **CLI:**
  - `dash0 apply -f <file|dir> [--dry-run]` validates every document before applying any. It accepts `Dashboard`, `PersesDashboard`, `CheckRule` and `PrometheusRule` as YAML or JSON.
  - Environment: `DASH0_API_URL`, `DASH0_AUTH_TOKEN`, `DASH0_DATASET`.
- **Still unverified, check against a live export:**
  - Markdown and Table plugin kinds.
  - Whether upstream `ListVariable` renders.
  - Whether subqueries work in dashboards (implied for check rules).
  - Whether `metadata.project` and datasource refs are ignored.
  - Whether `dash0Extensions.dataset` is honored.
  - Whether resource and data-point labels collide.

### 5.4 Perses

- Current release: v0.55.1.
- Dashboard: `kind: Dashboard`, `metadata.{name, project}`, `spec.{display, datasources, variables, panels, layouts, duration, refreshInterval}`. A panel is `kind: Panel` with a `spec.plugin` and `queries`. Layouts are `kind: Grid` with `items[{x, y, width, height, content: {$ref: "#/spec/panels/<key>"}}]`.
- **YAML is officially supported.**
- `percli lint` offline does structural checks only. Plugin specs are validated only with `--plugin.path` or `--online`.

## 6. Proposed golden translation (Postgres)

**Widget.** `avg:postgresql.connections{$scope} by {db}` becomes:

```
avg by (db_namespace) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})
```

- `$scope` is free-form with default `*`. It's dropped, with the warning `TEMPLATE_VARIABLE_DROPPED`.
- The panel is a `TimeSeriesChart` with `PrometheusTimeSeriesQuery`, in a 24-column grid.
- The other 8 widgets are reported per widget. The `system.*` ones are blocked as `MISSING_METRIC_MAPPING`, or as `UNSUPPORTED_UNIT_CONVERSION` because of the percent ↔ 0–1 scale.

**Monitor.** `percent_usage_connections` becomes the condition `avg_over_time((avg(<reviewed ratio expression>))[15m:1m]) > $__threshold`.

- Thresholds are `{degraded: 0.8, failed: 0.9}`, interval 1m, `for: 0s`, and `enabled: false` at first.
- The subquery keeps Datadog's order: aggregate across series first, then over time.
- Approximations listed in the report: `require_full_window`, `new_host_delay`, the subquery step, and message templates (kept as escaped literal text).

**Blocked example.** `replication_delay` gets `UNSUPPORTED_QUERY_FUNCTION` (`anomalies`) and is never published.

## 7. Open decisions (ask the user in free text)

1. **Target metric names, given the semconv gap.** Recommended: attribute names from semconv, server metric names, types and units from `postgresqlreceiver@v0.165.0`, and pairs cited from Datadog's metrics_mapping table. Whatever the inventory actually finds in Dash0 takes precedence. The alternative, strict semconv only, blocks nearly every Postgres widget and both monitors.
2. **Alert file format** (Perses has none). Recommended: a standard Prometheus rule group, where warning and critical become two rules with a `severity` label; it's valid in Dash0 as is. Publishing renders one Dash0 check rule (`thresholds{degraded, failed}` + `$__threshold`) from the same internal condition. The alternative is writing the Dash0 check-rule body directly.
3. **Monitor strictness.** Recommended: approximate and warn, for a reviewed allowlist only (`require_full_window`, `new_host_delay`, message templates as literal text; warning threshold → `degraded`). Everything else blocks import. The alternative is strict blocking, which leaves the golden monitor unpublished.

## 8. What's missing

**Postgres:**

| Area | Missing |
|---|---|
| Telemetry in Dash0 | **Unknown, the inventory is blocked.** If `postgresql.*` is absent, a demo feed is needed: `demo/docker-compose.yaml` with Postgres (`max_connections=20`) + otelcol-contrib v0.165.0 (`postgresqlreceiver`, `hostmetrics`) → Dash0 OTLP (`https://ingress.eu-west-1.aws.dash0.com`). It needs an ingest token, plus a script that opens idle connections to push usage past 0.8 and 0.9. |
| Mapping | No reviewed `mappings/datadog/postgres.json`. Golden entries: `postgresql.connections`→`postgresql.backends` (`db`→`db_namespace`, `host`→`server_address`), and `postgresql.percent_usage_connections`→ a derived ratio. Iteration 2 adds `rows_*` → `postgresql.operations{operation=…}` with `rate()`; the `tup_*` metrics are disabled by default. |
| Decisions | §7 items 1–3. |
| Dash0 format | One real dashboard export (gives variable, Markdown and Table kinds), and confirmation of the check-rule `thresholds`. |
| Fixtures | Postgres assets pinned to an integrations-core SHA, plus the license. |
| Code | Everything: package, provider, folder input, parser, Perses and rule writers, publish, tests. |
| Blocked by design | `replication_delay` (`anomalies`), `log_stream`, `top()` and `query_table` until they're supported. |

**Other services.** These are unknown until the inventory runs. Each one needs:

- target metrics present in Dash0;
- an integrations-core dashboard and monitor;
- rows in the metrics_mapping table;
- a reviewed mapping file;
- support for whichever widget and function types it uses.

The core pipeline is shared, so a new service is mostly a new mapping file.

## 9. Draft development plan (finalize after M0)

- **M0, Dash0 inventory (read-only).** Use the MCP tools in a new session, or a script with the endpoints in §5.3. Collect:
  - datasets;
  - `otel_metric_name` values;
  - `service_name` values;
  - `series` per prefix (`postgresql.`, `system.`, `db.client.`, `redis.`, `kafka.`, `jvm.`, `k8s.`, `http.`, `rpc.`, …) to get the attribute keys;
  - dashboards and check rules, with one dashboard read in full as the emitter reference.

  Raw responses go to `private-input/dash0-inventory/` (gitignored). The sanitized summary (names and counts only) goes to `docs/STATUS.md`.

  **Order of services.** Rank by: metrics present in Dash0 (required), then integrations-core dashboard and monitor exist, then metrics_mapping coverage, then simple query features.
  - If Postgres metrics are present, Postgres is the golden case.
  - If something else is present but Postgres isn't, the top-ranked service is the golden case; Postgres comes second, with M0b.
  - If nothing usable is present, do **M0b** (the demo feed) first.

- **M1, the service-independent core:**
  - Bootstrap TypeScript, Node 22, Commander, Zod, Vitest, tsx and `yaml`, plus a lockfile.
  - `SourceProvider` interface and table.
  - `--input <file|dir>`, repeatable: recursive `*.json`, sorted by relative path; recognized by shape; integrations-core wrapper unwrapped; anything else skipped with `UNSUPPORTED_ASSET_KIND`.
  - Writers:
    - `dashboards/<slug>.{json|yaml}` (Perses)
    - `rules/<slug>.{json|yaml}`
    - `report.json` and `manifest.json` (hashes, provider ID, compiler version)
    - Stable key order.
  - CLI:
    ```
    convert --source datadog --input <path>... --mapping <file> --out <dir> [--format json|yaml] [--publish] [--allow-partial]
    publish --from <dir> [--dry-run] [--allow-partial]
    ```
    The docs currently say `import`; rename it to `publish`.
- **M2, golden translation:** §6, with the fixtures and the reviewed mapping file. Mapping entry kinds are `gauge`, `rate` and `expression`; each entry has a `ref` and `verified` evidence.
- **M3, publish and verify live:**
  - Use Dash0 `import` endpoints, create-only, with receipts; uncertain outcomes are recorded as `unknown`, with no blind retry.
  - Read back with `GET`.
  - Before publishing, check every PromQL query with `format_query`, and with `query` returning data.
  - Evidence: the UI chart, and the check going degraded, then failed, on controlled values.
- **M4+, the edge-case ladder:**
  1. The rest of "Postgres - Metrics": multiple requests and queries, no-aggregator defaults, `rate` mappings, hostmetrics.
  2. The "Overview" screenboard: note → Markdown, query_value → StatChart, groups, `$db`/`$host` variables, `.rollup`, `.as_count`, formulas, `week_before`.
  3. The next ranked service.
  4. Datadog API fetch by ID, feeding the same `compile`.

**Verification:**

- `npm run typecheck && npm test`: parser, mapping, golden snapshots, double-run byte equality, folder order and unwrapping, the blocked `anomalies` case.
- `convert … --format yaml`, then `percli lint`.
- `dash0 apply --dry-run -f artifacts/…` with credentials.
- Live `publish`, then read back.

**Docs to update when planning is finalized:**

- `docs/PROJECT_HANDOFF.md`: Postgres golden example; folder input and YAML as P0; `import` → `publish`; Dash0 selector convention; alert output format; target vocabulary.
- `docs/EXECUTION_PLAN.md`: replace with the M0–M4 order.
- `docs/DEMO.md` and `docs/STATUS.md`: update to match.

## 10. First steps for the next session

1. Start a **new** session, not a resume, in `/Users/felix/tum/artemis/thinchackdash`, and confirm the `dash0` MCP tools load (ToolSearch `dash0`). Otherwise ask the user for a `.env` with a read-only token.
2. Run M0 and record the sanitized inventory in `docs/STATUS.md`.
3. Ask the user the §7 decisions in free text, and confirm the service order.
4. Finalize §9 and update the docs on a feature branch based on `worktree-provider-interface-docs`.
