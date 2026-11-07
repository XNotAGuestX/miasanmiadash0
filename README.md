# Datadog → Dash0 Migrator

**Highest priority, before anything else: deterministic conversion. No LLM shall be involved in translation from a source to Perses, PromQL, or Dash0 check rules—not even as an optional fallback. Reduce MVP scope before compromising this rule.** Codex and Claude may help write the implementation and tests; migration itself uses explicit parsers, mappings, and deterministic rules only.

A deterministic CLI that migrates Datadog dashboards and metric monitors to Dash0. Dashboards become Perses dashboards; metric monitors become Dash0 check rules and Prometheus rule groups. Every metric pair comes from an explicit, human-reviewed mapping file. Anything outside the supported subset is blocked with a diagnostic instead of being guessed.

**State (2026-11-07):**
- `convert` works offline and is covered by golden tests.
- `publish` has run live against Dash0: the Postgres check rule and both dashboards were imported and read back (plan 07 Task 5).
- `fetch` is implemented but has only been tested against a fake API; the live run waits on a Datadog account (B3).

See [STATUS.md](docs/STATUS.md) for details and [DEMO.md](docs/DEMO.md) for the demo runbook.

## Install and test

Needs Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/). Everything runs through one entry point, `uv run migrator <command>`:

```bash
uv sync                      # install runtime and dev dependencies
uv run migrator check        # ruff + mypy --strict + pytest
uv run migrator test -k parse    # pytest; extra args pass through
uv run migrator typecheck    # mypy --strict over src and tests
uv run migrator lint         # ruff
```

## Convert (offline)

```bash
uv run migrator convert --source datadog \
  --input fixtures/datadog/integrations-core/postgres \
  --mapping mappings/datadog/postgres.json --out /tmp/pg-out
```

Output of that command:

```text
PARTIAL    postgres-metrics 4/9 widgets
PARTIAL    postgres-overview 8/30 widgets
TRANSLATED postgres/monitors/percent_usage_connections.json monitor
BLOCKED    postgres/monitors/replication_delay.json monitor
total: dashboards 0 translated/2 partial/0 blocked, widgets 12 translated/0 partial/27 blocked, monitors 1 translated/0 partial/1 blocked, skipped files 0
```

`--input` takes files or folders, which are read recursively. `--out` must be empty. It receives:

- `dashboards/<slug>.json`: Perses dashboards, the Dash0 import body;
- `check-rules/<slug>.json`: Dash0 check-rule bodies, disabled and without an `id`;
- `rules/<slug>.prometheus.json`: Prometheus rule groups, warning then critical;
- `source/`: byte copies of the inputs;
- `report.json`: an outcome per dashboard, widget and monitor, plus every diagnostic;
- `manifest.json`: every file with its sha256 and whether it is eligible to publish.

Options: `--format yaml` writes the dashboards and Prometheus rules as YAML. `--project <name>` sets the Perses project; the default is `datadog-migration`.

Exit codes:
- `0`: everything translated;
- `2`: something partial or blocked;
- `1`: bad input, mapping or arguments.

The same inputs, mapping and version always produce the same bytes.

## Publish to Dash0

```bash
uv run migrator publish --from /tmp/pg-out --dry-run           # print the plan; send nothing
uv run migrator publish --from /tmp/pg-out --allow-partial     # import, including partial dashboards
uv run migrator publish --from /tmp/pg-out --dry-run --name-prefix demo-   # demo names: demo-Postgres - Metrics, …
```

> **Run live on 2026-11-07** (plan 07 Task 5): the Postgres check rule and both dashboards imported into `default` with `--name-prefix demo-`, read back equal, and a rerun reported `UNCHANGED`. See [STATUS.md](docs/STATUS.md#live-publish-plan-07-task-5-2026-11-07-2010-utc).

`publish` reads JSON output only: a run converted with `--format yaml` fails with "not valid JSON".

**What it sends:** translated dashboards and check rules from `manifest.json`. Partial dashboards go only with `--allow-partial`. Prometheus rule files and sources are never sent.

**`--name-prefix PREFIX`** (1–32 characters of `a-z`, `0-9`, `-`, e.g. `demo-`) prepends PREFIX to each dashboard's `metadata.name` and display name and to each check rule's name, at send time; the files, their sha256 and the manifest are unchanged, and the renamed body is validated again. Receipts record the prefix, and a rerun with a different prefix is refused. Use it for demo resources.

**How it sends them:**
- Before the first request, it checks every path, sha256 and schema.
- For each dashboard it also lists the dataset's dashboards (`GET /api/dashboards`) before and after the import, because the import response has no id.
- It is create-only: it never sends a dashboard's `metadata.dash0Extensions.id` or a check-rule `id`.
- Receipts in `<run dir>/import-results.json` make reruns safe. An imported asset reports `UNCHANGED`. A changed or ambiguous (`unknown`: a timeout or network error, any HTTP 5xx, or a 2xx without an ID) asset is refused until a human reconciles it. Only a 4xx counts as a definite failure that may be retried.
- HTTP 401 or 403 stops the run.

Exit codes:
- `0`: all imported or unchanged;
- `2`: something excluded;
- `1`: any failure, unknown result, refusal or validation error.

## Fetch from Datadog (read-only)

```bash
uv run migrator fetch --source datadog --dashboard-id abc-def-123 --monitor-id 4242 --out /tmp/dd-in
uv run migrator convert --source datadog --input /tmp/dd-in --mapping mappings/datadog/postgres.json --out /tmp/dd-out
```

> **Not yet run live.** Waits on a Datadog account (blocker B3). The argument and site validation paths have been run; the requests have only been tested against a fake API, including a fetch → convert round trip that matches the Postgres golden byte for byte.

**What it does:** downloads the selected dashboards and monitors unchanged, into `dashboards/<id>.json` and `monitors/<id>.json`.

**Safety checks:**
- Every ID, the site and the empty `--out` are validated before any request.
- Nothing is written unless every request succeeded.
- Errors carry the HTTP status, a hint (for example "needs the dashboards_read scope") and a body cut to 500 characters, with no key values.

Exit codes: `0` on success, `1` on any error.

## Environment variables

The CLI reads the process environment and doesn't load `.env` itself. Copy `.env.example` to `.env`, fill it in locally, and load it with `set -a; . ./.env; set +a`. Never pass secrets as arguments, and never commit them.

| Variable | Used by | Notes |
|---|---|---|
| `DASH0_API_URL` | `publish` | Your organization's API base URL (Settings → Endpoints); http(s), trailing `/` ignored |
| `DASH0_AUTH_TOKEN` | `publish` | Sent as `Authorization: Bearer`; redacted from every message |
| `DASH0_DATASET` | `publish` | Target dataset, e.g. `default` |
| `DD_API_KEY`, `DD_APP_KEY` | `fetch` | The application key needs `dashboards_read` / `monitors_read`; both are redacted from errors |
| `DD_SITE` | `fetch` | Bare host, default `datadoghq.eu` |
| `PG_CONTAINER`, `PGUSER`, `PGDATABASE`, `PGPASSWORD` | `scripts/hold-pg-connections.sh` | Demo only; passed into the container by name, never printed |

A missing variable gives `error: missing env: <NAMES>` and exit 1, without printing any values.

## Supported subset

**Assets:** Datadog dashboards in their raw JSON shape, and monitors either as the API's `definition` or wrapped as in integrations-core.

**Widgets:**
- `timeseries` becomes a `TimeSeriesChart`, `query_value` a `StatChart` and `note` a `Markdown` panel.
- `group` widgets are flattened into the grid.
- Other widget types (toplist, table, heatmap, …) are blocked with `UNSUPPORTED_WIDGET`.
- A widget is all or nothing: it never drops one of its series.

**Queries:**
- Supported form: `<avg|sum|min|max>:<metric>{<tag filters, $template vars>} by {<tags>}`.
- Formulas are limited to `+ - * /` over query names and numbers.
- Any query function (`anomalies`, `week_before`, `top`, …) blocks the query with `UNSUPPORTED_QUERY_FUNCTION`.
- A query without a space aggregator is blocked with `MISSING_AGGREGATOR`, because Datadog documents no default.

**Mappings** (`mappings/datadog/*.json`): each entry maps a Datadog metric to a Dash0 OTel metric. There are three kinds:
- `gauge`: a direct value;
- `rate`: `rate(...[$__rate_interval])` for per-second counters;
- `expression`: a reviewed PromQL template, such as the deduplicated connection ratio.

Entries can also carry fixed label matchers, unit scale, label renames and a deduplication grain. An unmapped metric or label blocks the query. Entries with `reviewed: null` still convert but carry an `UNREVIEWED_MAPPING` warning; only a human sets `reviewed`. Files exist for `postgres`, `kafka`, `docker`, `redis` and `nginx`.

**Monitors:**
- Supported: `query alert` / `metric alert` with `<avg|max|min|sum>(last_<n><m|h|d>):<query> <op> <number>`, a window ≤ 7 days, and options within the reviewed allowlist.
- They render as `<agg>_over_time((<query>)[<window>:1m]) <op> <threshold>`. The window stays in the expression, never in `for`.
- The inline threshold must equal `options.thresholds.critical`, and the warning must sit on the correct side of critical.
- Datadog `{{…}}` templates in the annotations are escaped, so Go templates print them rather than execute them.

## Known limits

- **Partial coverage by design.** The Postgres goldens translate 4/9 "Metrics" widgets and 8/30 "Overview" widgets. `report.json` names the reason for every block.
- **Monitor behaviour that isn't migrated:**
  - notifications and `@handles` (`NOTIFICATION_NOT_MIGRATED`);
  - no-data alerts, auto-resolve, renotify, escalation and recovery thresholds (all block the monitor);
  - a new-host grace period and full-window evaluation, which are only approximated (`MONITOR_OPTION_APPROXIMATED`).
- **Mappings need human review.** Every shipped entry is still `reviewed: null`.
- **Series churn.** After a collector restart, Dash0 can briefly hold two series for one instance. Sums must deduplicate first, as the Postgres entries do with `max by (service_instance_id, …)`; see [DASH0_INVENTORY.md caveat 2](docs/DASH0_INVENTORY.md#caveats).
- **Ephemeral demo data.** The `default` dataset has data only while the demo stack runs ([caveat 1](docs/DASH0_INVENTORY.md#caveats)).
- **Dash0 import contract (checked live 2026-11-07, plan 07 Task 1):** a check rule's id comes back at `id`. A dashboard import returns no id, so `publish` lists the dataset's dashboards before and after and takes the one new id with that `metadata.name`; anything else is `unknown`. Still open: whether Dash0 renders `{{…}}` in a check-rule `name`. Details in [STATUS.md](docs/STATUS.md#dash0-import-contract-live-plan-07-task-1-2026-11-07).
- **Validation level.** `report.validation` records syntax and schema checks only. API acceptance and semantics are proven separately (`docs/STATUS.md`).

## For contributors

1. Read [AGENTS.md](AGENTS.md), the shared working rules for humans, Codex and Claude. [CLAUDE.md](CLAUDE.md) points Claude to the same rules.
2. Read [the implementation plan overview](docs/handoff/README.md). Each numbered file in `docs/handoff/` is a self-contained, test-first plan.
3. Work is tracked in [GitHub issues](https://github.com/XNotAGuestX/thinchackdash/issues): one branch per issue, and every PR is reviewed by XNotAGuestX.
4. Background: [the project handoff](docs/PROJECT_HANDOFF.md), [the execution plan](docs/EXECUTION_PLAN.md), and the challenge requirements in [SOURCES.md](docs/SOURCES.md).

**Stack:**
- Python ≥ 3.13 with uv, one package (`src/migrator`) and one console script (`migrator`).
- Libraries: argparse, pydantic (strict), `promql-parser`, PyYAML.
- Tooling: pytest, mypy --strict, ruff.
- One `SourceProvider` interface is selected with `--source`; only `datadog` exists so far.
