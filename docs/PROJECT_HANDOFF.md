# Project initialization handoff

> **Superseded where it conflicts (2026-11-07):** the implementation plan is now [`docs/handoff/`](handoff/README.md). Where this document disagrees with it (first example, command names, priorities, phases), the handoff directory wins. This file stays as background.

## Non-negotiable first priority

**Deterministic conversion is of utmost importance and comes before anything else. No LLM shall be involved in translation from any source to Perses.** The same prohibition covers source-query-to-PromQL and source-monitor-to-check-rule conversion. MVP deadlines, broader coverage, and demo goals never justify an exception.

Every conversion step must use explicit parsing, reviewed static mappings, deterministic transformation rules, and validation. No model calls, agent-mediated conversion, inferred mappings from a model, optional AI translation, output repair by a model, or LLM fallback are allowed. Unsupported or ambiguous constructs produce diagnostics and are excluded from automatic conversion until explicit rules are implemented.

Codex and Claude may help write and review implementation code and tests. They must not process migration inputs into target assets as part of the migration workflow. Identical source inputs, mappings, configuration, and compiler version must yield identical target artifacts and diagnostics. This requirement governs every milestone below.

## Outcome

Build a CLI that ingests Datadog dashboards and metric monitors, deterministically compiles the supported subset into Perses dashboards and Dash0 check rules using PromQL, explains incompatibilities, and imports the results into Dash0.

The proof is one source dashboard and one source monitor visible and functional in Dash0, plus a clear unsupported-feature report. Any LLM involvement in conversion violates the project requirement, including a hybrid deterministic/LLM approach. Codex and Claude may implement and review the project; neither is part of the migration runtime.

Business strategy, commercial analysis, and pitch preparation are owned separately. This handoff covers engineering, verification, the technical demo, and submission readiness.

## Starting state and decisions

At initialization on 2026-11-07:

- The local worktree had no project files. Its configured remote was `git@github.com:XNotAGuestX/thinchackdash.git`, on branch `main`.
- The required [starter repository](https://github.com/vimouzin/dash0-dashboard-migrator) showed only a README. No starter runtime or stack was available to preserve.
- These documents initialize the project; they do not implement the migrator or establish fork ancestry.

Use Python 3.13 managed by uv: argparse for the CLI, pydantic for boundary validation, pyyaml, pytest, mypy --strict and ruff. Use the standard library for HTTP, one package, JSON configuration, and ordinary local files. Pin dependency versions in the committed `uv.lock` (`uv add` / `uv sync`; no `pip install`), and record the interpreter in `.python-version`.

Do not spend hackathon time comparing equivalent frameworks. Change the defaults only for a concrete team constraint or existing implementation, and record the decision in `STATUS.md`.

## Scope and priority

| Priority | Capability | Completion evidence |
| --- | --- | --- |
| First, non-negotiable | Fully deterministic conversion with zero LLM involvement | Parser/rule/mapping path reviewed; repeated outputs match; no model-based conversion or fallback exists |
| P0 | JSON file ingestion for one dashboard and one monitor | Sanitized fixtures compile offline |
| P0 | Datadog API ingestion by explicit dashboard/monitor IDs | Selected assets fetched and retained unchanged |
| P0 | Flat metric timeseries widget → Perses chart | Chart renders a supported query in Dash0 |
| P0 | Explicit metric/label/unit mappings | Output references telemetry confirmed in the target dataset |
| P0 | Narrow deterministic dashboard and monitor query grammar | Expected PromQL and rejection tests pass |
| P0 | One static critical-threshold metric monitor → check rule | Imported check has the intended expression and threshold |
| P0 | Machine-readable and terminal migration report | Every source item is accounted for |
| P0 | Official Dash0 imports and read-back | Destination IDs and UI evidence recorded |
| P0 | Reproducible technical demo and usage docs | Another contributor can run the supported path |
| P1 | Query-value widget, more aggregators, simple layout fidelity | Added only after P0 works end to end |
| P1 | Warning + critical thresholds, explicit label grouping, counters | Each feature has semantic tests and a verified target form |
| P1 | Folder input and broader API discovery | Reuses the same compiler; no alternate conversion path |
| P2 | YAML, formulas, template variables, extra vendors (as new source providers), UI | Defer unless all P0 and useful P1 work is complete |

No general-purpose Datadog parser, automatic universal OTel metric mapping, notification routing migration, historical telemetry migration, or production monitoring cutover is promised.

## First supported example

Choose a synthetic gauge with an explicit target counterpart and the same unit. Suggested example names below are team-defined demo metrics, **not OpenTelemetry semantic convention names**.

```text
Dashboard query:
max:demo.temperature{env:demo}

Monitor query:
max(last_5m):max:demo.temperature{env:demo} > 75

Explicit mapping:
demo.temperature -> demo_temperature_celsius
env -> environment
type: gauge; source and target units: degrees Celsius; scale: 1

Dashboard PromQL:
max(demo_temperature_celsius{environment="demo"})

Monitor condition PromQL:
max(max_over_time(demo_temperature_celsius{environment="demo"}[5m])) > 75
```

Use identical controlled samples in both platforms when possible. Confirm the target metric name and label names by querying the actual dataset; adapt the mapping to what exists rather than assuming a collector's naming transformation.

The monitor uses a rolling lookback and one critical threshold. Import the first check disabled, then enable only the demo check during live verification. Show low/high input values and the corresponding result. Record differences caused by sampling, interpolation, missing data, and evaluation timing. Do not advertise universal equivalence from this example.

## Architecture

```text
            --source <id>  (selects one provider from a static table)
                          |
       +------------------+----------------------------------------------+
       | Source provider (P0: datadog only; owns all source-specific     |
       | logic): fetch by ID / load files -> source validation ->        |
       | bounded parser -> provider model -> explicit mapping -> compile |
       +------------------+----------------------------------------------+
                          |  shared output contract
          +---------------+-------------------+--------------------+
          v                                   v                    v
 Perses dashboard JSON            PromQL check condition    diagnostics + item outcomes
          +---------------+-------------------+--------------------+
                          |
              validation + manifest + report           (shared)
                          |
   Dash0 check-rule body rendering, explicit import -> read-back   (shared)
```

### Source provider interface

**Decision (2026-11-07, user):** translation does **not** need to be source-agnostic. There is no vendor-neutral intermediate model. Each source provider owns its source-specific parsing, model, mapping and translation from start to finish, so a common abstraction never limits source-specific semantics. The shared requirement is one interface for choosing a provider, plus the shared output contract it produces.

```ts
// src/migrator/source/provider.py — illustrative; finalize the types during bootstrap
interface SourceProvider {
  readonly id: string; // value of --source, e.g. "datadog"
  // Online read of explicitly selected assets; original JSON retained unchanged.
  fetch(selection: SourceSelection, env: SourceEnv): Promise<SourceAsset[]>;
  // Offline file ingestion; returns the same shape as fetch.
  load(files: SourceFiles): SourceAsset[];
  // Pure and deterministic: no network, clock, randomness, or model calls.
  // The provider validates its own mapping format.
  compile(assets: SourceAsset[], mapping: unknown): CompileResult;
}

// CompileResult = Perses dashboards + PromQL check conditions
//               + per-item outcomes + diagnostics (shared types in src/migrator/target.py)
const providers: Record<string, SourceProvider> = { datadog: datadogProvider };
```

- `fetch` and `compile` require `--source <id>`. An unknown ID fails with exit `1` and lists the known IDs. The provider ID and compiler version are recorded in `report.json` and `manifest.json`. `import` reads the provider ID from the manifest only for reporting; it has no source logic.
- `fetch` and `load` return the same asset shape, so API and file inputs go through the same `compile`.
- Shared code (CLI, report, manifest, validation, destination) depends only on `SourceProvider` and the shared output types. Only `source/provider.py` imports a provider's directory, and providers don't import each other.
- Diagnostic codes and fields are shared; a provider may add codes, and `sourcePath` uses the provider's own JSON paths.
- Adding a vendor means one new provider directory and one table entry. This is a static interface, not a plugin framework: no dynamic loading, discovery, or config-driven registration. Other vendors remain P2.

Keep each provider's model limited to its supported subset. Do not build a general compiler framework.

Suggested implementation tree, **not files currently implemented**:

```text
src/
  cli.py                  # arguments, --source selection, command wiring, exit status
  source/provider.py      # SourceProvider interface + static providers table
  source/datadog/         # the only P0 provider; all Datadog-specific translation
    __init__.py           # datadogProvider: implements SourceProvider
    api.py                # read dashboard/monitor by ID; retain original JSON
    files.py              # load one exported asset per file
    parse_query.py        # tokenizer + bounded grammar; full input consumption
    model.py              # parsed Datadog Query, Widget, Monitor
    mapping.py            # validate/load the Datadog telemetry mapping JSON
    compile_query.py      # typed query -> PromQL
    dashboard.py          # flat supported widgets -> Perses
    monitor.py            # narrow monitor subset -> PromQL check condition
  target.py               # shared output types: Perses dashboard, check condition, Diagnostic, outcomes
  promql.py               # shared PromQL label-value escaping and selector rendering
  destination/dash0.py    # check-rule body rendering, import and read-back; no translation logic
  validation.py           # output and manifest boundaries
  report.py               # item accounting, summary, artifact manifest
fixtures/
  datadog/                # synthetic dashboard and monitor; incompatibility cases
  mappings/               # explicit demo mapping
  expected/               # reviewed expected translations
tests/                    # behavior and HTTP contract tests
```

Treat these paths as module boundaries, not a requirement to create empty files. Keep imports and interfaces small enough for two contributors to coordinate easily.

## Translation contract

### Source assets

- Accept one raw Datadog dashboard object and one raw metric monitor object, each in JSON. File ingestion and API ingestion must feed the same compiler.
- API scope is read-by-ID first: `GET /api/v1/dashboard/{dashboard_id}` and `GET /api/v1/monitor/{monitor_id}`. Broad discovery is later work.
- Retain source IDs, titles, descriptions, widget IDs/indices, queries, layout, monitor thresholds, and original JSON. Private exports go in ignored `private-input/` or `artifacts/`.
- Validate required fields while preserving unknown source fields for reporting. Classify unknown fields: harmless metadata can be retained; unrecognized query/alert behavior is not silently accepted.

### Dashboard queries

Initial grammar:

```text
query      := aggregate ":" metric "{" filters "}"
aggregate  := "avg" | "min" | "max" | "sum"
filters    := "*" | tag ":" literal ("," tag ":" literal)*
```

Implement the `max` happy path first. Allow metric/tag identifier characters found in the fixtures, consume the entire input, and reject unsupported quoting, wildcard patterns, negation, OR filters, grouping, functions, formulas, and template variables with a diagnostic. Expand grammar only with corresponding tests.

- P0 accepts explicitly mapped gauges only. Counters, distributions, `.as_rate()`, `.as_count()`, percentiles, and rollups are blocked initially.
- Translate exact-match filters with correct PromQL string escaping. Never interpolate raw source text into a label selector.
- Preserve the selected space aggregation; reject conflicting or absent mappings.
- Support the timeseries widget's single direct metric request first. Named queries, formulas, mixed data sources, and multiple requests must be handled explicitly or mark that entire widget unsupported. Never drop a series and call the widget fully migrated.
- Use a known-good Dash0-exported chart as the emitter reference. Preserve titles/descriptions and source ordering. A simple grid is sufficient; report layout changes. Styling fidelity is secondary.
- A dashboard containing an unsupported widget is `partial`, with that widget omitted and listed in the report. If no usable panels remain, it is `blocked` and has no importable dashboard artifact.

### Metric and label mapping

The Datadog provider owns its mapping format: a small versioned JSON contract, validated by a strict pydantic model. The `source` field must match the selected `--source`; a mismatch blocks compilation. Another provider may define its own format.

```json
{
  "version": 1,
  "source": "datadog",
  "metrics": {
    "demo.temperature": {
      "target": "demo_temperature_celsius",
      "type": "gauge",
      "sourceUnit": "Cel",
      "targetUnit": "Cel",
      "scale": 1,
      "labels": { "env": "environment" }
    }
  }
}
```

For P0 require matching source/target units and `scale: 1`; reject other scales with `UNSUPPORTED_UNIT_CONVERSION`. A later conversion must transform queries and thresholds consistently, not merely rename a unit. Missing mappings or tag mappings block the affected item. Validate destination metric/label existence during the live demo, separately from offline compilation. Map to real OTel conventions only when type, unit, dimensions, and meaning have been checked.

### Monitors and alerts

Initial monitor grammar is deliberately narrower than dashboard grammar:

```text
max(last_Nm):max:<mapped-gauge>{<exact-match-filters>} > <number>
```

Parse the lookback duration, space/time aggregation, comparator, and finite numeric threshold. Check the inline threshold against `options.thresholds.critical`; a disagreement blocks the monitor. Permit only ordinary metric alerts with the documented supported option values. Maintain an explicit allowlist of supported semantic options/defaults based on the chosen source fixture; reject non-default behavior outside it.

- Preserve the rolling lookback in the expression. **Do not convert `last_5m` into `for: 5m`.** The latter is a pending duration, not a query window. See [Prometheus alert semantics](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).
- Keep evaluation interval distinct from lookback and pending duration. Record the demo interval and target timing; do not claim to preserve an implicit source cadence without evidence.
- No-data notifications, custom missing-data behavior, recovery thresholds, renotification, scheduling, evaluation delay, full-window differences, grouped alerts, composite monitors, and anomaly/forecast functions require explicit diagnostics. Do not silently discard meaningful source behavior.
- Initially support one critical threshold. Warning thresholds block the monitor until their mapping is implemented and tested.
- Preserve plain text name/message as summary/description where supported. Datadog template expansions and notification mentions require manual review; do not route notifications automatically.
- Keep a standard PromQL condition internally. Render Dash0's check-rule API body separately; it is not a raw Prometheus YAML rule group.
- P0 can use an inline critical comparison in `expression`. Dash0 also has a `$__threshold` extension; use that only after verifying the exact `thresholds` schema and behavior. Avoid implementing both variants during the first slice.

### Destination contract

Use the organization's actual API base URL and an explicit dataset. The official [dashboard import](https://www.dash0.com/docs/api-reference/operations/post/api/import/dashboard) takes a Perses-compatible `Dashboard` object. Confirm panel/query plugin support with an actual Dash0 export and rendered chart; a free-form `spec` accepted by an API is insufficient validation.

The official [check-rule import](https://www.dash0.com/docs/api-reference/operations/post/api/import/check-rule) uses fields such as `name` and `expression`, with optional `enabled`, duration, and metadata fields. Verify the schema at implementation time, especially ID placement; documentation prose and examples can differ. Record request/response contract fixtures with secrets removed.

- Import only emitted, validated, eligible artifacts. Default to rejecting an incomplete bundle. An explicit `--allow-partial` may import supported complete assets/partial dashboards, never a blocked monitor.
- Start with create-only requests that omit destination IDs. A supplied ID can change overwrite behavior. No implicit update-by-title.
- Persist returned IDs, source references, artifact hashes, dataset, and API host in an ignored run manifest. On a repeat invocation, skip recorded successful imports of unchanged artifacts for that destination. Reject changed artifacts with existing receipts until an explicit update flow exists.
- This is local duplicate prevention, not guaranteed server idempotency. A timeout after a possible write is `unknown`; reconcile by destination inspection before retrying. Do not auto-retry POST after an ambiguous failure.
- Stop on authentication/dataset errors. Record per-asset results if one creation succeeds and another fails. No automatic rollback deletion is required.

## CLI and artifact contract

**Proposed commands, to be implemented.** Every command goes through the `migrator` console script: `uv run migrator <command>` (see [00-context §5](handoff/00-context.md#5-stack)).

```sh
# Online source read; credentials come from environment variables.
uv run migrator fetch --source datadog --dashboard-id DEMO_ID --monitor-id 123 --out private-input/demo

# Offline deterministic compilation; no network calls or destination writes.
uv run migrator compile --source datadog --dashboard private-input/demo/dashboard.json --monitor private-input/demo/monitor.json --mapping fixtures/mappings/demo.json --out artifacts/demo

# Inspect outputs, then check the import plan without creating anything.
uv run migrator import --input artifacts/demo --dry-run

# Explicit destination write, using env-configured API host, dataset, and token.
uv run migrator import --input artifacts/demo
```

Also permit offline compilation directly from committed synthetic fixtures. Require at least one source asset; dashboard-only/monitor-only runs are valid for development. Produce:

```text
artifacts/demo/
  source/                 # exact input copies; private and ignored
  dashboards/<source-id>.json
  check-rules/<source-id>.json
  report.json             # compilation outcomes, diagnostics, validation levels
  manifest.json           # artifact paths/hashes and eligibility
  import-results.json     # destination receipts; created only during import
```

Constrain artifact paths to the run directory and validate the manifest before import. Keep compile output independent of authentication data and import receipts.

### Reporting

Every source dashboard, widget/query, and monitor needs a stable source reference and outcome: `translated`, `partial`, or `blocked`. Import state is separate: `not_attempted`, `imported`, `failed`, or `unknown`. Do not count widgets as dashboards or translated assets as imported assets.

Each diagnostic includes `code`, `severity`, `sourceId`, `sourcePath`, `message`, and `suggestedAction`, plus original query text when safe. Use paths such as `widgets[0].definition.requests[0].q`. Example codes:

`UNSUPPORTED_WIDGET`, `UNSUPPORTED_QUERY_FUNCTION`, `MISSING_METRIC_MAPPING`, `MISSING_LABEL_MAPPING`, `UNSUPPORTED_UNIT_CONVERSION`, `UNSUPPORTED_MONITOR_OPTION`, `THRESHOLD_MISMATCH`, `TARGET_VALIDATION_FAILED`, `IMPORT_FAILED`, `IMPORT_RESULT_UNKNOWN`.

Track validation separately as `syntax`, `schema`, `api`, and `semantics`, each with `passed`, `failed`, or `not_run` and supporting evidence where applicable. Offline compilation does not set `api` or `semantics` to passed.

Print a short summary to the terminal and write full JSON detail. Exit `0` for complete success, `1` for execution/schema/API failure, `2` for a completed run with blocked or partial source coverage. An allowed partial import still exits `2`. Never suppress a failed import behind a successful compilation count.

## Definition of done

- [ ] Highest-priority invariant holds: no LLM participates in any conversion step, including optional paths, mapping inference, repairs, or fallbacks.
- [ ] Identical source inputs, mappings, configuration, and compiler version produce identical target artifacts and diagnostics.
- [ ] Source/API and file paths feed the same deterministic compiler.
- [ ] The source provider is selected through the `SourceProvider` interface (`--source`); shared report, manifest, and import code contain no Datadog-specific logic.
- [ ] One real Datadog dashboard and monitor are fetched, compiled, imported, and read back.
- [ ] The target dashboard displays actual demo telemetry; the check condition is verified with controlled values.
- [ ] The original query, emitted PromQL, mapping, and threshold/window behavior can be explained.
- [ ] An unsupported example generates a precise diagnostic and is excluded from import.
- [ ] No runtime LLM calls or credentials appear in code, fixtures, logs, or committed output.
- [ ] Focused tests, type checking, and build pass with documented commands.
- [ ] Another contributor can reproduce the offline path without credentials and the live path with their own credentials.
- [ ] Actual limitations and remaining semantic differences are documented.
- [ ] Required fork, feature branch, upstream PR, usage instructions, and technical evidence are ready for submission.

Until live evidence exists, describe the result as an offline compiler or integration in progress, not a completed migration.
