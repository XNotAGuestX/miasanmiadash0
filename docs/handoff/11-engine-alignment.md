# 11 — Engine alignment: implementation plan

**Goal:** make each translation demonstrably right, using cheap and deterministic evidence first and an LLM opinion only at the end.

**Order:** 1 → 2 → 3 → 4 → 5. Each step gets its own issue and PR. Step 5 comes last and is advisory only.

**Rules that apply to every step:**
- Nothing here runs inside `migrator convert`.
- Steps 4 and 5 read a finished run directory and write a separate file next to it.
- They never change dashboards, rules, `report.json`, `manifest.json` or exit codes (`AGENTS.md`).

---

## Step 1 — Mappings: check against Datadog's own OTel table

Source: [OpenTelemetry Metrics Mapping](https://docs.datadoghq.com/opentelemetry/mapping/metrics_mapping.md). Its columns are `otel`, `datadog`, `filter`, `transform` and `integration`.

- [ ] `scripts/pin_otel_mapping.py`: download the page once and parse its table. Keep only the rows for our prefixes (`postgresql.`, `redis.`, `kafka.`, `nginx.`, `container.`, `docker.`, `system.`, `jvm.`). Write `fixtures/datadog/otel-mapping.yaml` with a header giving the URL and fetch date, then commit it.
- [ ] `tests/datadog/test_vendor_mapping.py`: for every mapping entry whose Datadog metric is in the table, assert two things:
  - `target.name` is one of the table's `otel` names for that metric;
  - a `× 100` transform means `scale: 100`.
  A mismatch fails unless the entry's `ref` contains `vendor deviation: <reason>`. Filters are only printed, because attribute names differ between receiver versions (`state` vs `cpu_mode`).
- [ ] `--gaps` option: list the Datadog metrics used in `fixtures/cases/` that the table covers but no mapping has. Add each one by hand, citing its table row.

**Done when** the test passes for all five mapping files, and the gap list is empty or every gap has an issue.

## Step 2 — Evidence: what each metric measures, offline

- [ ] Extend `scripts/pin-integrations-core.sh` to also pin each service's `metadata.csv` (same SHA). It gives the Datadog metric type and unit.
- [ ] Test: `kind: rate` requires a Datadog type of `rate` or `count`, and `kind: gauge` requires `gauge`. This catches a missing `rate()` and `rate()` on a gauge.
- [ ] Per entry, before setting `reviewed`, record both sides in `ref`:
  - the Datadog check's query or stat (integrations-core file at the pinned SHA);
  - the OTel receiver's query or stat (collector-contrib v0.165.0);
  - the unit on each side.

  A coding assistant may find the code; a human decides.

**Done when** the type test passes and every reviewed entry names both sources.

## Step 3 — Rules: documented semantics, functions by frequency

- [ ] Merge the default aggregator first: branch `default-avg-aggregator`, #33.
- [ ] Then one issue per function, in order of how often the pinned dashboards use it:

  | Function | Uses |
  |---|---|
  | `.weighted()` | 36 |
  | `top()` | 10 |
  | `.as_count()` | 9 |
  | `.as_rate()` | 8 |
  | `abs()` | 6 |
  | `.rollup()` | 5 |
  | `.fill()` | 5 |

  Each issue contains:
  - a quote of the Datadog documentation;
  - the exact PromQL equivalent, or the reason the function stays blocked;
  - the change in `parse_query.py` or `compile_query.py`;
  - exact tests with a toy mapping in `tests/datadog/test_compile_query.py`;
  - regenerated goldens.
- Starting points; decide each from the documentation:

  | Function | Starting point |
  |---|---|
  | `abs()` | `abs()` |
  | `.as_rate()`, `.as_count()` | depend on the Datadog type from step 2 |
  | `top()` | ranks over the whole window while `topk` ranks per step, so not exact |
  | `.rollup()` | needs a range other than `$__rate_interval`, so it is a rule decision |
  | `.fill()` | probably stays blocked |

**Done when** each function is either translated with tests or blocked with a documented reason.

## Step 4 — Smoke check: plausible data in Dash0 (read-only)

- [ ] `scripts/smoke_check.py <run dir> [--start ISO --end ISO]`:
  1. For every panel query in the run's dashboards, substitute `$__rate_interval` → `5m` and variables → `.*`.
  2. Call `GET $DASH0_API_URL/api/prometheus/api/v1/query_range` with the header `Dash0-Dataset`.
  3. Record the series count and the min and max value.
  4. Flag `no_data`, `nan`, a negative rate or count, and a percent above 100.
  5. Write `<run>/smoke.json`, print one line per panel, and exit 1 on any flag.

  The token comes from the environment and is never printed.
- [ ] Tests with a fake HTTP sender, as in `tests/destination/`.
- Data exists only in the 2026-11-07 14:05–15:21 UTC window until durable telemetry arrives (B2).

**Done when** the Postgres run shows data for every translated panel, or each flag has an issue.

## Step 5 — Agent0 review: "was the conversion successful?" (advisory, last)

- [ ] `scripts/agent0_check.py <run dir>`: reuse `McpAgent0` from `scripts/run_oracle.py`. Per dashboard, send one prompt containing, for each panel:
  - the Datadog widget queries;
  - the converted PromQL;
  - its smoke result.

  Ask for YAML per panel: `verdict: same | different | unsure` and `reason`. Write `<run>/agent0-check.json`.
- [ ] Keep the flags separate from every deterministic result:
  - `different` or `unsure` panels are listed under "Agent0 flags" for a human;
  - a failed Agent0 call is recorded as `agent0: error`, not as a failure.

  Nothing else reads the file. Agent0's answer never changes a translation; a fix goes through steps 1–3.
- [ ] Tests with a fake Agent0, as in `tests/scripts/test_run_oracle.py`.

**Done when** the Postgres run produces `agent0-check.json`, and every `different` has a human decision (converter fix, mapping fix, or dismissed with a reason).

## Out of scope

A live Datadog-versus-Dash0 comparison lab, LLM triage or voting, and automatic fixes from Agent0 answers.
