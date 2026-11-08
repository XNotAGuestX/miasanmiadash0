# On-demand live comparison

`scripts/live_compare.py` starts the full OpenTelemetry Demo, collects its metrics once,
exports them to Datadog and Dash0, converts configured Datadog assets with the existing
offline compiler, publishes demo-prefixed assets, verifies read-back and compares results.
It stops its containers after completion or a handled interruption. No model participates.

Implementation task: [#146](https://github.com/XNotAGuestX/thinchackdash/issues/146), expanding
[horizon #122](https://github.com/XNotAGuestX/thinchackdash/issues/122) at Felix's request.
This tests selected conversions using shared OTel samples. It does not establish equivalence
between independent native vendor collectors or verify actual alert delivery.

## Run

Prerequisites: uv, Docker Engine/Desktop with Compose, approximately 6 GB available RAM
and 14 GB disk for the full demo, outbound access to GitHub/GHCR and both vendors, an
existing **demo** Dash0 dataset, and vendor credentials. Containers expose ports only on
localhost with automatically allocated host ports. Existing stacks are left alone.

First validate configuration and source/target pairing offline:

```sh
uv run scripts/live_compare.py \
  --dataset-config scripts/live/datasets/otel-demo.yaml \
  --tests scripts/live/suites/default.yaml \
  --dash0-dataset migration-demo \
  --out out/live/demo-01 --dry-run
```

Export these variables in your shell (or explicitly load a private, gitignored `.env`):

| Variable | Purpose |
|---|---|
| `DD_SITE` | Datadog site, defaults to `datadoghq.eu` |
| `DD_API_KEY` | Metrics ingestion and query API key |
| `DD_APP_KEY` | Application key with `timeseries_query` permission |
| `DASH0_API_URL` | Explicit HTTPS API URL from your organization's endpoints |
| `DASH0_OTLP_ENDPOINT` | Explicit HTTPS OTLP/HTTP **base** endpoint, without `/v1/metrics` |
| `DASH0_AUTH_TOKEN` | Token with ingestion, query and import access to the demo dataset |

Run the same command without `--dry-run`. `--dash0-dataset` selects the dataset for
ingestion, queries and publication, overriding `DASH0_DATASET`. The script never creates
datasets or modifies source assets. It publishes all source assets configured in the suite;
repeatable `--case redis-memory --case connection-monitor` selects comparisons.

The default measurement takes about 17 minutes after startup: five minutes warm-up, ten
minutes measurement and two minutes ingestion allowance. Progress is printed every 30 seconds.
Image downloads and initial health checks add startup time.

Exit codes: **0** all selected comparisons and read-backs passed; **2** comparison failures
or blocked conversions; **1** configuration, credentials, HTTP, Docker or cleanup failure.
An API-accepted dashboard with no data cannot pass. Missing Datadog integration aliases or
tags fail explicitly; no mapping is inferred and tolerances never widen automatically.

## Define datasets and tests independently

All paths inside configuration files are relative to the configuration file itself.
Unknown configuration keys and invalid values are rejected.

Workload profiles, such as `scripts/live/datasets/otel-demo.yaml`, define:

- `users`, `spawn_rate`, `collection_seconds`;
- enabled `receivers`: `postgresql`, `redis`, `nginx`, `kafkametrics`, optionally
  `hostmetrics` and `docker_stats` (the latter two mount host resources read-only);
- `seed_sql`: local SQL files applied to the isolated `astronomy_db` database with
  `ON_ERROR_STOP=1`, after startup and before warm-up;
- `feature_flags`: optional complete [flagd configuration](https://flagd.dev/reference/flag-definitions/)
  JSON file replacing the extracted demo's flag definitions. The original file is untouched.

The pinned full application stack and load generator stay the same across profiles.
The upstream feature-flag UI's mount is read-only so tests use the configured flags.
Additional observability backends and AI demo extras are not started. Only metrics are
exported to the vendors; application traces and logs are consumed locally by a nop exporter.

Test suites, such as `scripts/live/suites/default.yaml`, define `inputs`, `mappings`, timing
and an independent list of `cases`. Inputs are normal Datadog source JSON files/folders;
the existing compiler decides which constructs translate. `source` is the exact manifest
`sourceId`: an individually supplied file uses its filename; a folder uses `folder/path.json`.
Dashboards must fully translate to be published by this harness.

```yaml
version: 1
inputs: [../assets/dashboard.json]
mappings: [../../../mappings/datadog]
warmup_seconds: 300
window_seconds: 600
settle_seconds: 120
step_seconds: 60
rate_interval: 5m
cases:
  - id: connections
    source: dashboard.json
    request: /widgets/0/definition/requests/0
    formula_index: 0
    panel: widget-0
    query_index: 0
    variables: {host: $run}
    series_labels: {}
    mode: window_mean
    relative_tolerance_pct: 3
    absolute_tolerance: 0
    require_nonzero: true
```

`request` is a JSON pointer to the source request. `formula_index` selects a displayed
formula (or query when formulas are absent). `panel` and `query_index` reference the
**generated** Perses output. The harness checks the source widget indices and flattened
displayed-query ordering; a missing or inconsistent pair is rejected.

`variables` supplies literal values for declared source variables; `$run` means the generated
run ID. Source values must fit the supported literal tag grammar; unsafe substitutions are
rejected. Target regex values are escaped and JSON-encoded. Both executed expressions are
scoped to the run's `host`/`host_name` through their parsed syntax trees. Scoping happens at
execution time, before target series deduplication; artifacts and their hashes stay unchanged.

`series_labels` explicitly pairs grouping tags and labels, for example `{db: postgresql_database_name}`.
The source query must actually group by that tag, and the account must expose it. No label
correspondence is inferred. Extra series, missing groups and ambiguous keys fail.

`mode` is `window_mean` or `per_bucket`. Every matched series must have a finite sample at
every requested timestamp; no interpolation, nearest-point matching or dropped nulls.
Comparisons use the half-open historical interval `[start, end)`, on an aligned UTC grid.
Datadog is asked for the same interval as Dash0; a backend changing that grid fails coverage.
Default comparison uses each series' arithmetic mean on this common grid:

```text
abs(Dash0 - Datadog) <= max(absolute_tolerance, abs(Datadog) * relative_tolerance_pct / 100)
```

Set both tolerances to zero for exact numeric equality. With zero Datadog values, only
the absolute tolerance applies. `require_nonzero` defaults to true to prevent idle zero
signals from appearing convincing; set it to false for explicitly expected zero results.
Ranges are recorded for inspection; they do not substitute for the chosen comparison.

For a metric monitor, set `kind: monitor` and omit `request`/`panel`. The harness uses the
existing monitor parser, computes its source lookback reducer on the same step grid, and
queries the numeric left-hand side of the read-back check. Lookbacks must fit warm-up and
align to the query step. Threshold decisions must agree at **every** timestamp independently
of numeric tolerances. Checks remain disabled; actual evaluation scheduling, no-data policy,
and notifications are not verified by these numeric tests.

## Evidence, resumption and cleanup

The ignored output directory contains:

- `compiled/`: ordinary deterministic source copies, manifest, report, generated artifacts
  and the publisher's `import-results.json`;
- `state.json`: run ID, configuration/input fingerprint, fixed measurement window and
  collection/publication progress;
- `runtime/`: verified upstream source and isolated Compose/collector files;
- `comparison.json` and `comparison.md`: selected expressions, dataset, returned asset IDs,
  read-back outcomes, coverage, means/ranges, differences and threshold decisions.

Evidence is separate from compiler snapshots. Vendor response bodies are not saved in it;
credentials are inherited by the collector without being written into Compose. Run artifacts,
raw telemetry and credentials must not be committed. Current mappings keep their existing
review status; numerical evidence does not automatically set `reviewed`.

Rerun the identical command and output directory to resume. Completed collection reuses the
same historical window, and unchanged publication receipts prevent duplicate imports. Changed
inputs, mappings, compiler output, suite, selected cases, destination or profile require a new
output directory. A process lock prevents concurrent ownership of one output directory.

An ambiguous import receipt blocks retry. If the process died while publication was in
flight, `publicationInFlight` also blocks resumption even if no receipt was written. Inspect
Dash0 and reconcile every possibly created asset/receipt first; only then clear that marker
in `state.json`. Do not clear receipts to force a retry.

Normal completion and SIGINT/SIGTERM stop the owned project, including local volumes.
`--keep-running` explicitly retains it. For retained containers or an uncatchable process
kill, take `runId` from `state.json` and stop only that project:

```sh
docker compose -p <runId> -f <out>/runtime/compose.json down --volumes --remove-orphans
```

Dash0 assets are retained with their recorded IDs. Remote deletion is a separate explicit
operation. A cleanup failure yields exit 1 and is recorded in the evidence.

## Upstream pins and validation

The source is [OpenTelemetry Demo 3.1.0](https://github.com/open-telemetry/opentelemetry-demo/releases/tag/3.1.0),
commit `dedc0178918e260823323b8d95005a8cb924b007`, archive SHA-256
`60bc2420ede659375b54302799fc312443345457a6894b26ba5c2d7acc6895f7`.
`scripts/live/images.lock.json` pins all application/dependency image indexes; the official
Collector is overridden to `0.160.0`, matching the repository's metric definitions. Upstream
copyright and Apache-2.0 notices remain in the extracted source. No images are built.

The Datadog branch uses its supported exporter and its documented
[PostgreSQL cumulative-to-delta/rate processing](https://docs.datadoghq.com/opentelemetry/integrations/postgres_metrics/).
These rules are independent of migrator mappings. Dash0 receives the original cumulative
samples through its OTLP/HTTP endpoint and `Dash0-Dataset` header. Queries follow the official
[Datadog timeseries API](https://docs.datadoghq.com/api/latest/metrics/query-timeseries-data-across-multiple-products/)
and the repository's verified Dash0 Prometheus API contract.

Offline checks:

```sh
uv run migrator check
uv run ruff check scripts/live_compare.py scripts/live_compare_support
uv run mypy --strict scripts/live_compare.py scripts/live_compare_support
```

Focused tests use fake vendor APIs and stubbed Docker operations. They never establish live
parity. A real two-vendor run requires configured credentials and recorded IDs/read-back/
numeric evidence. At implementation time Datadog credentials were unavailable, so live
Datadog/Dash0 parity remains unverified.
