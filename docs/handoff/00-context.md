# 00 — Shared context and spec

Every implementation plan in this directory argues from this file. If a plan conflicts with it, this file wins. If this file conflicts with an older doc (`PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, `DEMO.md`), this file wins. The overview is in [README.md](README.md).

## 1. Goal

Build a **deterministic converter from Datadog dashboards to Perses**, the open-source dashboard standard:

- It's a CLI that reads Datadog dashboard JSON (files or folders) and writes Perses dashboards (JSON or YAML), plus a migration report.
- Dash0 is where converted dashboards are checked against real telemetry, and the optional publish target.
- Datadog metric monitors convert too, into Prometheus rule groups and Dash0 check rules. They're secondary to the dashboard converter.

## 2. Rules (from `AGENTS.md`; these are not negotiable)

1. **No LLM takes part in any conversion step.** That covers source → Perses, query → PromQL and monitor → rule, including optional, repair and fallback paths. Coding assistants write code, tests and mapping tables. They never translate migration inputs at runtime.
2. The same input, mapping, options and compiler version must give byte-identical artifacts and diagnostics.
3. Unsupported or ambiguous input gives a diagnostic and is blocked. It's never guessed. Parse the whole input; never translate a recognized prefix and ignore the rest.
4. No inferred telemetry equivalence. Every metric and label pair comes from a mapping file that a human has reviewed.
5. The compiler is offline: no network, no clock, no randomness. Only `publish` writes to Dash0.
6. Keep secrets out of Git, logs and reports. Use the environment variables in `.env.example`.

## 3. Decisions

| # | Decision | Status |
|---|---|---|
| D1 | Translation need not be source-agnostic. There's one `SourceProvider` interface with a static table selected by `--source`; Datadog is the only provider. | User decision, 2026-11-07 |
| D2 | Golden examples come from DataDog/integrations-core, starting with Postgres. | User decision |
| D3 | Inputs are files or folders. | User decision |
| D4 | Output is JSON, YAML, or a direct publish to Dash0. The default format is Perses. | User decision |
| D5 | Order the services by the data that exists in Dash0: Postgres → host → Kafka → Redis → nginx → Docker. | Derived from [DASH0_INVENTORY.md](../DASH0_INVENTORY.md#service-order) |
| D6 | The core target is the dashboard converter; alerts are secondary. | User confirmation, 2026-11-07 |
| A1 | Target vocabulary: metric names and labels **exactly as found in Dash0** (postgresqlreceiver 0.160.0 labels). Each pair is cited from Datadog's [metrics_mapping](https://docs.datadoghq.com/opentelemetry/guide/metrics_mapping/) table and reviewed by a human. | **Assumed default**, waiting for the user |
| A2 | Alert output: a Prometheus rule group file **and** a Dash0 check-rule body, both rendered from one internal condition. | **Assumed default**, waiting for the user |
| A3 | Monitor strictness: approximate with a warning for a reviewed allowlist of options; block everything else. | **Assumed default**, waiting for the user |
| A4 | CLI verbs: `convert` (offline) and `publish` (writes to Dash0). They replace `compile` and `import` in the older docs. | From the planning handoff |
| B1 | A Dash0 API token scoped to dataset `default` (or a manual UI export of one dashboard, for the reference only) | **Open blocker** for plan 07 and the plan 05 gates |
| B2 | An owner for the local OTel Demo telemetry, and approval for the connection-holder script | **Open blocker** for plan 09 |
| B3 | A Datadog EU account and keys | **Open blocker** for plan 10 only |

## 4. Repository layout (agreed module boundaries)

```text
pyproject.toml                     # package metadata, deps, mypy/ruff/pytest config, uv_build backend
uv.lock                            # committed lockfile (uv)
.python-version                    # 3.13, the interpreter uv uses
src/migrator/
  cli.py                     # argparse wiring, exit codes; also the test/typecheck/lint/check commands
  convert.py                 # run_convert(): input → provider → writers → report
  input.py                   # collect files from --input paths (sorted, recursive)
  target.py                  # shared output types (Perses, rules, Diagnostic, outcomes)
  promql.py                  # label-value escaping and selector rendering
  write.py                   # stable JSON/YAML writers, slugs, sha256
  report.py                  # report.json, manifest.json, terminal summary
  validation.py              # pydantic models for emitted Perses dashboards and rules
  version.py                 # COMPILER_VERSION
  source/provider.py         # SourceProvider interface + static table
  source/datadog/__init__.py # datadogProvider
  source/datadog/assets.py   # recognize, unwrap and identify Datadog assets
  source/datadog/model.py    # parsed query/monitor types
  source/datadog/parse_query.py
  source/datadog/mapping.py
  source/datadog/compile_query.py
  source/datadog/dashboard.py
  source/datadog/monitor.py
  destination/dash0.py       # publish + read-back (plan 07 only)
mappings/datadog/<service>.json   # reviewed mapping files
fixtures/datadog/integrations-core/<service>/...   # pinned source assets
fixtures/datadog/synthetic/...    # small hand-written edge cases
fixtures/expected/<case>/...      # reviewed expected outputs
tests/...                          # pytest (test_*.py)
```

## 5. Stack

- Python ≥ 3.13 (`requires-python = ">=3.13"` in `pyproject.toml`, pinned to `3.13` in `.python-version`), one package `migrator` under `src/`, fully typed (`py.typed`, `mypy --strict`).
- **uv** manages the interpreter, the virtualenv, dependencies and the build (`uv_build` backend). Commit `uv.lock`; add dependencies with `uv add <pkg>` (dev: `uv add --dev <pkg>`), never with `pip install`.
- Libraries: `pydantic` (boundary validation), `pyyaml` (YAML output), `promql-parser` (PromQL syntax check). The CLI uses the standard-library `argparse`; HTTP uses the standard library.
- Dev tooling: `pytest`, `mypy`, `ruff`, `types-pyyaml`.
- Commands, all through one entry point (`[project.scripts] migrator = "migrator.cli:main"`):
  - `uv sync`: create `.venv` and install runtime + dev dependencies.
  - `uv run migrator convert --source datadog --input <path>... --mapping <file> --out <dir>`
  - `uv run migrator test [pytest args]`, for example `uv run migrator test tests/datadog -k parse`.
  - `uv run migrator typecheck` (mypy --strict), `uv run migrator lint` (ruff), `uv run migrator check` (lint + typecheck + test).
- **Reading the plans.** Some interface and test snippets in plans 01–10 are still written as TypeScript. They specify behaviour and names, not syntax: implement them in Python with snake_case names (`runConvert` → `run_convert`), dataclasses or pydantic models for interfaces, `Literal` unions for string-literal types, and pytest tests. Zod maps to pydantic, Lezer PromQL to `promql-parser`, `node:crypto` to `hashlib`, `fetch` to `urllib.request`.

## 6. Source facts (Datadog)

**Pinned assets.** Use DataDog/integrations-core at commit **`a9b9e42b7e484861ecbd1f5919da7c52a694b74d`** (BSD-3-Clause; include the notice).

**Dashboard JSON (raw, not wrapped).**

- Top-level keys: `title`, `description`, `layout_type: "ordered"`, `template_variables: [{name, prefix, default}]`, `widgets[]`.
- Widget: `{definition: {type, title, requests[]}, layout?: {x, y, width, height}}`. Datadog uses a 12-column grid. The Postgres dashboards have no `layout`.
- Request (new format): `{response_format: "timeseries", queries: [{data_source: "metrics", name: "query1", query, semantic_mode?}], formulas: [{formula: "query1"}]}`.
- Request (legacy format): `{q: "<query>"}`.

**Monitor JSON.**

- integrations-core wraps monitors: `{version, created_at, last_updated_at, title, tags, description, definition}`. `definition` has the API shape `{name, type: "query alert", query, message, options, tags, priority}`.
- Golden monitor `postgres/assets/monitors/percent_usage_connections.json`:
  - `query`: `avg(last_15m):avg:postgresql.percent_usage_connections{*} > 0.9`
  - `options`: `{escalation_message: "", include_tags: true, locked: false, new_host_delay: 300, no_data_timeframe: null, notify_audit: false, notify_no_data: false, renotify_interval: "0", require_full_window: true, thresholds: {critical: 0.9, warning: 0.8}, timeout_h: 0}`
  - Name and message contain `{{host.name}}` and `{{#is_alert}}…{{/is_alert}}`.
- Blocked monitor `replication_delay.json`: `avg(last_1h):anomalies(avg:postgresql.replication_delay{*}, 'basic', 2, …) >= 1`.

**Golden dashboard "Postgres - Metrics"** (`postgres/assets/dashboards/postgresql_dashboard.json`): 9 timeseries widgets.

| Index | Title | Requests → queries / formulas |
|---|---|---|
| 0 | Rows fetched / returned / inserted / updated (per sec) | 4 requests, each `avg:postgresql.rows_{fetched,returned,inserted,updated}{$scope}`, formula `query1` |
| 1 | Connections | 1 request: `avg:postgresql.connections{$scope} by {db}`, formula `query1` |
| 2 | Inserts / updates / deletes (per sec) | 1 request: `postgresql.rows_{inserted,deleted,updated}{$scope}` (no aggregator), formulas `query1..3` |
| 3 | Disk utilization (%) | `avg:system.io.util{$scope}` |
| 4 | System load | 3 requests: `system.load.{1,5,15}{$scope}` (no aggregator) |
| 5 | CPU usage (%) | 1 request: `system.cpu.{idle,system,iowait,user,stolen,guest}{$scope}` (no aggregator), formulas `query1..6` |
| 6 | I/O wait (%) | `max:system.cpu.iowait{$scope}` |
| 7 | System memory | `sum:system.mem.usable{$scope}`, `sum:system.mem.total{$scope}`; formulas `query1`, **`query2 - query1`** |
| 8 | Network traffic (per sec) | 2 requests: `sum:system.net.bytes_{rcvd,sent}{$scope}` |

## 7. Target facts (Perses and Dash0)

**Perses dashboard** (reference: Dash0 fixture `dash0hq/dash0-cli@3e0651f`, `internal/testutil/fixtures/dashboards/get_success.json`):

```json
{"kind":"Dashboard","metadata":{"name":"<slug>","project":"<project>"},
 "spec":{"display":{"name":"<title>","description":"<desc>"},"duration":"1h","variables":[],
  "panels":{"<key>":{"kind":"Panel","spec":{"display":{"name":"<title>","description":""},
    "plugin":{"kind":"TimeSeriesChart","spec":{}},
    "queries":[{"kind":"TimeSeriesQuery","spec":{"plugin":{"kind":"PrometheusTimeSeriesQuery","spec":{"query":"<promql>"}}}}]}}},
  "layouts":[{"kind":"Grid","spec":{"items":[{"x":0,"y":0,"width":12,"height":8,"content":{"$ref":"#/spec/panels/<key>"}}]}}]}}
```

- The grid is 24 columns wide. The Dash0 import body is the same object.
- In Dash0, `metadata.dash0Extensions.id` would overwrite an existing dashboard, so never emit it.

**Dash0 PromQL conventions** (verified against live data):

- Select a metric as `{otel_metric_name="<dotted.name>", otel_metric_type="<sum|gauge|histogram|…>"}`. A bare dotted name doesn't work.
- Attribute keys become labels with dots replaced by `_`.
- Use `rate(<sel>[$__rate_interval])` for monotonic sums.

**Real labels in the `default` dataset** (see [DASH0_INVENTORY.md](../DASH0_INVENTORY.md)):

- Postgres: `postgresql_database_name`, `postgresql_table_name`, `operation`, `source`, `service_instance_id`, `host_name`.
- Host: `cpu_mode`, `system_memory_state`, `system_network_direction`, `system_device`.
- Kafka JMX: `type`, `service_instance_id`.

**Check rule (Dash0 API body, unverified until plan 07):**

```json
{"name": "...", "expression": "... > $__threshold", "thresholds": {"degraded": 0.8, "failed": 0.9}, "interval": "1m", "for": "0s", "enabled": false, "labels": {}, "annotations": {"summary": "...", "description": "..."}}
```

- Omit `id`; publishing is create-only.
- Limits: `summary` ≤ 255 characters, `description` ≤ 2048 characters.

## 8. Shared output contract

**Outcomes.** Each item (dashboard, widget, monitor) has one: `translated | partial | blocked`. Only a dashboard can be `partial`. A widget or monitor is all or nothing; never drop a series.

**Diagnostic fields:** `{code, severity: "error"|"warning"|"info", sourceId, sourcePath, message, suggestedAction, sourceText?}`.

- `sourcePath` uses the JSON path inside the source asset, e.g. `widgets[1].definition.requests[0].queries[0].query`.
- Diagnostics are ordered by item order, then by source path, then by emission order.

**Diagnostic codes**, with the plan that introduces each:

| Code | Severity | Plan |
|---|---|---|
| `UNSUPPORTED_ASSET_KIND` | warning | 01 |
| `DUPLICATE_SOURCE_ID` | error (exit 1) | 01 |
| `INVALID_JSON` | error (exit 1) | 01 |
| `UNSUPPORTED_QUERY_SYNTAX` | error | 02 |
| `UNSUPPORTED_QUERY_FUNCTION` | error | 02 |
| `MISSING_AGGREGATOR` | error | 03 (relaxed in 05) |
| `MISSING_METRIC_MAPPING` | error | 03 |
| `MISSING_LABEL_MAPPING` | error | 03 |
| `UNSUPPORTED_UNIT_CONVERSION` | error | 03 (relaxed in 05) |
| `TEMPLATE_VARIABLE_DROPPED` | warning | 03 |
| `UNSUPPORTED_TEMPLATE_VARIABLE` | error | 03 |
| `UNREVIEWED_MAPPING` | warning | 03 |
| `UNSUPPORTED_WIDGET` | error | 04 |
| `UNSUPPORTED_DATA_SOURCE` | error | 04 |
| `UNSUPPORTED_FORMULA` | error | 04 |
| `LAYOUT_APPROXIMATED` | info | 04 |
| `OPTION_IGNORED` | info | 04 |
| `TARGET_VALIDATION_FAILED` | error | 04 |
| `DEFAULT_AGGREGATOR_APPLIED` | warning | 05 |
| `UNSUPPORTED_MONITOR_TYPE` | error | 06 |
| `UNSUPPORTED_MONITOR_OPTION` | error | 06 |
| `MONITOR_OPTION_APPROXIMATED` | warning | 06 |
| `THRESHOLD_MISMATCH` | error | 06 |
| `NOTIFICATION_NOT_MIGRATED` | warning | 06 |
| `TEXT_TRUNCATED` | warning | 06 |
| `IMPORT_FAILED` | error | 07 |
| `IMPORT_RESULT_UNKNOWN` | error | 07 |

**Validation levels** in the report: `syntax`, `schema`, `api` and `semantics`, each `passed | failed | not_run`. `convert` never sets `api` or `semantics`.

**Exit codes:**

- `0`: every item translated.
- `2`: the run finished with a partial or blocked item.
- `1`: bad arguments, an unreadable input, an invalid mapping, an unknown `--source`, a duplicate source ID, or an API failure.
