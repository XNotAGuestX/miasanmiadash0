# Shared project status

Last updated: 2026-11-07: Track A implemented on branch `worktree-track-a` (Python/uv converter; see the Track A handoff entry below). Earlier: all plan tasks, open decisions and blockers filed as GitHub issues (#1–#62); from now on work is tracked and discussed in [issues](https://github.com/XNotAGuestX/thinchackdash/issues). Earlier: two-person work split added ([`handoff/WORK_SPLIT.md`](handoff/WORK_SPLIT.md)). Earlier: implementation plan written and split into handoffs in [`handoff/`](handoff/README.md). Dash0 inventory (M0) done ([DASH0_INVENTORY.md](DASH0_INVENTORY.md)).

Highest-priority requirement: deterministic conversion before all other objectives. No LLM involvement in source-to-Perses or query/alert conversion, including optional inference, repair, and fallback paths. Shared rules, handoff, kickoff prompt, and acceptance gates now state this explicitly. Codex and Claude remain implementation assistants only.

## Actual state

| Area | State | Evidence |
| --- | --- | --- |
| Project scope and handoff | Written | `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, `DEMO.md` |
| Implementation plan | Written; awaiting the user's review and confirmation of assumed defaults A1–A4 | [`handoff/README.md`](handoff/README.md) maps plans 00–10; research notes in [`PLANNING_HANDOFF.md`](PLANNING_HANDOFF.md) |
| Dash0 inventory (M0) | Done (read-only, via MCP) | [`DASH0_INVENTORY.md`](DASH0_INVENTORY.md): `default` has live Postgres (27 metrics), Kafka (broker JMX and consumer lag), Redis, Nginx, host, Docker and HTTP-check data from a local OTel Demo run; `dash0-demo` has no database metrics. Service order: Postgres → host → Kafka → Redis → Nginx → Docker |
| Shared Codex/Claude rules | Written | Root `AGENTS.md`; `CLAUDE.md` refers to it |
| Local configuration template | Written | Root `.env.example` and `.gitignore` |
| Starter/fork relationship | Unresolved | Current remote is `XNotAGuestX/thinchackdash`; required starter differs |
| CLI/runtime/package | Working offline (`convert`); no `publish`/`fetch` | Python ≥ 3.13 + uv; single entry point `uv run migrator {convert,test,typecheck,lint,check}` (`pyproject.toml`, `uv.lock`) |
| Fixtures/parser/compiler | Dashboards done (plans 02–04, 05.T2–T8, 06.T3); monitors done in review (plan 06 T1–T2, T4–T5, PRs #77–#80): golden `fixtures/expected/postgres-monitors/`, `percent_usage_connections` translated, `replication_delay` blocked | Pinned integrations-core postgres, kafka, docker_daemon at `a9b9e42`; synthetic fixtures; mappings `postgres.json`, `kafka.json`, `docker.json`, all `reviewed: null` |
| Datadog API integration | Not started | No credentials or live source evidence checked |
| Dash0 API/schema spike | Done live (plan 07 Task 1, 2026-11-07) | Two demo imports to `default` with a scoped token; see "Dash0 import contract (live)" below. Sanitized responses in `fixtures/dash0/live-2026-11-07/` |
| Telemetry and semantic validation | Data present, not durable | `default` has data since 2026-11-07 14:06 UTC from one `docker-desktop` host. Connection usage is about 0.08; no controlled threshold crossing exists yet |
| Automated checks | Green | `uv run migrator check`: ruff clean, mypy --strict clean, pytest unit tests passing. Oracle suite (`tests/unit`, unreviewed cases skipped) runs against the converter; see "Oracle test suite handoff". Golden: `fixtures/expected/postgres-p1/` (Postgres dashboards, byte-equal and determinism tests), in review |
| Submission | Not started | No commit, push, fork, or PR created by the handoff task |

Handoff verification: all eight Markdown files passed local link, heading-anchor, and code-fence checks. Git ignore checks confirmed that `.env`, `.env.local`, run artifacts, and private inputs are excluded. These are documentation/configuration checks, not application or live migration tests.

## Current ownership

Ownership lives in GitHub issues: the assignee of an issue is its driver, and the branch is named in the issue. See `AGENTS.md`, "Tracking work in GitHub issues" and "Branches and merging".

| View | Link |
| --- | --- |
| Project board (Status, Priority, Size, Track, Plan, Phase) | [thinchack-Dash0](https://github.com/users/XNotAGuestX/projects/3) |
| Track A tasks | [`track:A`](https://github.com/XNotAGuestX/thinchackdash/issues?q=is%3Aopen+label%3Atrack%3AA) |
| Track B tasks | [`track:B`](https://github.com/XNotAGuestX/thinchackdash/issues?q=is%3Aopen+label%3Atrack%3AB) |
| Plans (epics with sub-issues) | [`epic`](https://github.com/XNotAGuestX/thinchackdash/issues?q=is%3Aopen+label%3Aepic) |
| Decisions and blockers | [#1](https://github.com/XNotAGuestX/thinchackdash/issues/1) A1–A4, [#2](https://github.com/XNotAGuestX/thinchackdash/issues/2) starter/fork, [#3](https://github.com/XNotAGuestX/thinchackdash/issues/3) B1, [#4](https://github.com/XNotAGuestX/thinchackdash/issues/4) B2, [#5](https://github.com/XNotAGuestX/thinchackdash/issues/5) B3 |

## Oracle test suite handoff (2026-11-07, Claude)

- **Aligned with PR #85 (2026-11-07, Claude for Felix; #85 is the source of truth):** `feature/oracle-tests` now has PR #85 (`worktree-track-a`, up to `a6010fb`) merged in, with #85's `pyproject.toml`, `.python-version` (3.13), `uv.lock` and `src/migrator/__init__.py` unchanged except for the opt-in `oracle` group. **Merge #85 first**; this branch then only adds the oracle suite. The tests now call #85's public API (`parse_query.parse_metric_query`, `mapping.parse_mapping`, `dashboard.compile_dashboard`); request and widget cases are derived in `tests/support.py`. `scripts/build_expected.py` applies #85's mapping-independent rules (no default aggregator → `MISSING_AGGREGATOR`, widget option `time`, parse errors, variable promotion with anchored matchers) and the mapping file names `docker.json` / `redis.json`; widgets without requests can be reviewed by override. Expectations: 65/207 requests, 89/251 leaf widgets translated. 23 request-level disagreements with #85 remain, all mapping-dependent; see [`REVIEW.md`](../fixtures/expected/REVIEW.md) "Converter rules and disagreements". Checks: `uv run migrator check` → ruff clean, mypy --strict clean, 404 passed, 621 skipped with `--group oracle` (403/622 without; the MCP SDK test skips); `uv run pytest --include-unreviewed tests/unit`: parser 262/262 pass, failures only in unreviewed Postgres/Docker/Kafka cases (nginx/Redis skip until #76 adds their mappings).
- **Setup (uv, 2026-11-07):** `uv sync` (uv-managed CPython 3.13 from `.python-version`, deps from `uv.lock`, group `dev` by default; `uv sync --group oracle` adds the Agent0 MCP client). Run `uv run migrator check` (unreviewed cases skipped) or `uv run pytest --include-unreviewed`. Full guide: [`tests/README.md`](../tests/README.md).
- **Pipeline:** `scripts/extract_cases.py` (pinned dashboards → `fixtures/cases/`) → `scripts/render_oracle_prompt.py <svc>/<id>` (fixed template `fixtures/oracle/PROMPT.md` → `prompt.md`) → ask Agent0 → save verbatim `fixtures/oracle/agent0/<svc>/<id>/answer.yaml` → `scripts/build_expected.py <svc>/<id>` (rules overlay → `fixtures/expected/<svc>/<id>/expected.yaml`). Human decisions go in `overrides.yaml` next to it.
- **Agent0 done, all 9 dashboards** (answer + expected built): `postgres/postgresql_dashboard`, `postgres/postgresql_screenboard_dashboard`, `nginx/NGINX-Metrics_dashboard` (Dash0 UI chat); `nginx/NGINX-Overview_dashboard`, `nginx/plus_overview`, `redisdb/overview`, `docker_daemon/docker_dashboard`, `kafka/kafka_dashboard`, `kafka/kafka_kraft_dashboard` (dash0 MCP `runTask`, ~17:43–17:45 local, thread links in each `answer.yaml` header). No YAML quoting fixes were needed for the six MCP answers; every prompt `source_path` is answered.
- **Expected outcomes (unreviewed):** 69/207 requests translated, 98/251 leaf widgets translated, all 9 dashboards `partial`. Per dashboard (requests translated/total): Postgres Metrics 13/15, Postgres Overview 11/29, NGINX Metrics 6/7, NGINX Overview 7/9, NGINX Plus 5/22, Redis 18/29, Docker 6/20, Kafka 1/35, Kafka KRaft 2/41.
- **Function rule (2026-11-07, Claude, user-approved):** `scripts/build_expected.py` now blocks every request that uses a Datadog function (`ALLOWED_FUNCTIONS` is empty), matching plans 02/03/05. That flipped 20 Agent0 translations to blocked (`weighted` 9, `as_count` 4, `top` 2, `per_second` 2, `rollup`/`per_minute`/`diff`/`abs` 1 each), each with an overlay note keeping Agent0's PromQL. `fixtures/oracle/PROMPT.md` gained a "Hard rules" block (functions, no extra constants, only `$__rate_interval`, `rate()` only on monotonic sums, derived metrics and grain go in `notes`, prefixed variables → `=~"$name"`). The 9 recorded `prompt.md`/answers are unchanged (state hashes still match the old template); a default `run_oracle.py` run only warns that prompts changed. Use `--full` to ask Agent0 again with the new rules.
- **OTel catalog rule (2026-11-07, Claude, user-requested):** a missing metric is only blocked if OpenTelemetry defines no equivalent at all. Pinned definitions in `fixtures/otel/` (collector-contrib v0.165.0 receivers + `scraper/zookeeperscraper`, semantic-conventions v1.45.0 `model/**/*metrics.yaml`, java-contrib v1.62.1 jmx-scraper Kafka rules; `NOTICE.md`) → `scripts/build_otel_catalog.py` → `fixtures/otel/catalog.yaml` (694 metrics). Dataset snapshot `fixtures/oracle/dash0_default_metrics.yaml` (256 metrics for the relevant prefixes, dash0 MCP `getMetricCatalog`, 14:00–15:30Z). `build_expected.py`: OTel metric in the dataset → as before; only in the catalog → stays `translated` with a `dataset: {available: false, missing_metrics, otel_sources}` block and a note; in neither → `blocked` `MISSING_METRIC_MAPPING`. `PROMPT.md` now lets Agent0 use catalog metrics (new answer fields `in_dataset`, `otel_source`; validated by `run_oracle.py` when present) and lists per-dashboard candidates (static Datadog prefix → OTel prefix table in `render_oracle_prompt.py`). Rebuilding with the **existing** answers changes nothing (they only use dataset metrics); the effect needs a new Agent0 run: `uv run scripts/run_oracle.py --full` with `DASH0_AUTH_TOKEN` (not available in this session). Checks: `tests/scripts` 37 passed (8 new in `test_build_expected.py`).
- **Checks (2026-11-07, before the #85 alignment; superseded):** `.venv/bin/pytest -q --include-unreviewed` → 963 collected, 0 collection errors, **963 failed**, all with `ModuleNotFoundError: No module named 'migrator.source'` (expected red; no engine yet). By file: `test_parse_query.py` 262, `test_request.py` 414 (207 × 2), `test_widget.py` 251, `test_dashboards.py` 36 (9 × 4). By milestone: p0 265, p1 44, p2 654. Default `.venv/bin/pytest -q` → 262 failed (parser cases, not oracle-gated), 701 skipped (unreviewed).
- **Docs:** [`fixtures/expected/REVIEW.md`](../fixtures/expected/REVIEW.md) (per-dashboard tables + flagged deviations), [`tests/README.md`](../tests/README.md), `handoff/00-context.md` §4/§5 now Python/pytest (with a TS → Python name table for plans 01–10).
- **Data caveat:** receiver data in `default` only exists 2026-11-07 ~14:05–15:21 UTC (OTel demo stopped). Live checks used that window. Not in the dataset at all: MySQL, MongoDB, Elasticsearch, Kubernetes.
- **Known deviations to review** (details in REVIEW.md "Decide these first"): no dedup grain on `postgresql.connections` (plan 05 wants one); CPU via `rate(system.cpu.time)` instead of `system.cpu.utilization` × 100; Agent0-added scaling constants (`100 *`, `/ 1e7`); translated Datadog functions `as_count`, `rollup(max)`, `per_second`, `per_minute`, `diff`, `top`, dropped `.weighted()`, `abs`; derived metrics (NGINX dropped = accepted − handled, Plus active = active − waiting); Redis expired vs evicted inconsistency; Kafka JMX `.rate` → `rate()`; hard-coded 15m window in NGINX Overview.
- **Remaining blockers:** (1) human review of REVIEW.md → `overrides.yaml` with `reviewed: true` (request-less widgets by widget `source_path`); until then the oracle cases stay skipped. (2) nginx and Redis mappings (`mappings/datadog/nginx.json`, `redis.json`) arrive with PR #76; their cases skip until then. (3) every #85 mapping entry has `reviewed: null`, so translated cases also expect `UNREVIEWED_MAPPING` to disappear after the mapping review. (4) user decision on adding MySQL/MongoDB/Elasticsearch/Kubernetes data.
- **Batch oracle runner (2026-11-07, Claude):** `scripts/run_oracle.py [fixtures/oracle/dashboards.json] [-j N] [--retries N] [--full] [--case SVC/ID] [--adopt-existing] [--dry-run]`. Input JSON lists the dashboards (`{"dataset", "model_class", "reasoning_effort", "dashboards": [{"case": "<svc>/<id>"}]}`). It runs N dashboards in parallel against the dash0 MCP server (`runTask` → `waitForTask`), validates each YAML answer against the case (every `source_path` answered, PromQL count = formula count), writes `prompt.md` + verbatim `answer.yaml`, then rebuilds `expected.yaml`. Progress is tracked in `fixtures/oracle/agent0/state.json` (status, thread ID, prompt sha256, attempts, last error). A default run asks only for cases that are not `done` and resumes `pending` threads; `--full` asks again for all. Retries use exponential backoff: a transport error retries the same thread, an invalid answer opens a new thread. State is seeded with all 9 existing answers (`--adopt-existing`); the recorded prompts match the current template. Run with `uv run scripts/run_oracle.py`; needs the `oracle` group (`mcp==2.3.0`, installed by `uv sync`) and `DASH0_AUTH_TOKEN` (read access) in the environment or `.env`. Checks: `uv run pytest -q tests/scripts` → 29 passed (fake Agent0 plus an in-process MCP server through the real SDK). **Not yet run live:** no token is available, so the HTTP/auth path to Dash0 is untested. `scripts/build_expected.py` gained a `write(key)` helper (same output).
- **Next:** merge PR #85, then this branch; a human decides the 23 disagreements and reviews REVIEW.md into `overrides.yaml` (p0 first: `postgres/postgresql_dashboard/widgets[1]`), then `uv run pytest -m p0`.

## Next concrete action

Follow [`handoff/README.md`](handoff/README.md):

1. The user reviews the plans and confirms or changes the assumed defaults A1–A3 (target vocabulary, alert output, monitor strictness) and A4 (`convert` / `publish` command names).
2. Claim the plan 01 issues ([epic #6](https://github.com/XNotAGuestX/thinchackdash/issues/6)) and execute plans 01 → 02 → 03 → 04 (the offline MVP converter). No credentials needed.
3. In parallel, resolve blockers B1 (Dash0 token), B2 (demo telemetry owner) and B3 (Datadog account, plan 10 only).

The starter/fork workflow is still unresolved; settle it before the first implementation commit.

## Recorded decisions

- 2026-11-07 (user): translation does not need to be source-agnostic. Datadog is the only P0 source. Each source provider owns its parsing, mapping, and translation; the requirement is one `SourceProvider` interface with a static table selected by `--source`, plus shared output types (Perses dashboards, PromQL check conditions, diagnostics, outcomes). If a shared contract would limit Datadog functionality, discuss it with the user before compromising features. Contract: `PROJECT_HANDOFF.md`, section "Source provider interface".

## Known blockers and decisions to resolve

- No hackathon deadline or engineering time budget was supplied; use the proportional plan and record the actual deadline when known.
- **Demo telemetry isn't durable** (M0). `default` data exists only while one machine (`docker-desktop`) runs the OTel Demo stack. It needs an owner or an always-on host.
- **No controlled threshold crossing.** Postgres connection usage is about 0.08, against thresholds of 0.8 and 0.9. It needs a connection-holder script; changing the thresholds isn't allowed.
- **Series deduplication.** Resource-hash churn after a collector restart makes `sum` double-count. The reviewed ratio must deduplicate (`PLANNING_HANDOFF.md` §6).
- ~~**Dash0 token missing.**~~ Resolved 2026-11-07 (B1): the user created a token, kept only in the gitignored `.env`.
- **Datadog credentials unset.** P0 uses integrations-core files pinned to `a9b9e42b7e484861ecbd1f5919da7c52a694b74d`. API fetch stays at M4+.
- Target labels are settled by the data: postgresqlreceiver 0.160.0, legacy `postgresql_database_name` and `postgresql_table_name`. The user still needs to confirm this (`PLANNING_HANDOFF.md` §7.1).
- This branch is 2 `.gitignore` commits behind `main`. Reconcile it before implementation.
- Stack changed to Python + uv (user instruction, 2026-11-07). The handoff's TypeScript names map to Python modules; pydantic replaces Zod, `promql-parser` replaces Lezer PromQL. `00-context.md` §5 still describes TypeScript.
- `AGENTS.md` Definition of Done still says `npm test` / `npm run typecheck`; with the Python stack the equivalent is `uv run migrator check` (ruff + mypy --strict + pytest).
- Semantics, manual read-only check (2026-11-07, dataset `default`, data until ~15:10 UTC): the converted Connections query (with grain) returned `astronomy_db` ≈ 5 and `postgres` ≈ 3–4; the `percent_usage_connections` ratio returned ≈ 0.08. Not recorded in `report.validation.semantics`. Second check for the P1 golden (2026-11-07 ~17:54 UTC): Connections `astronomy_db` = 5, `postgres` = 3; widget 0 `rate(postgresql.tup_fetched)` ≈ 84.7/s; widget 6 I/O wait ≈ 0.47 %; widget 8 network receive ≈ 886 kB/s. Semantics: manual check.
- Every mapping entry (`postgres.json`, `kafka.json`, `docker.json`) has `reviewed: null` and needs a human review before goldens are frozen.
- ~~The official check-rule documentation has differing ID references in prose and schema.~~ Settled live: the import response carries the new id at `id` (see below).

## Dash0 import contract (live, plan 07 Task 1, 2026-11-07)

Run by Claude with the user's go-ahead, one POST each, no retry, dataset `default`. Read-only calls before that: `GET /api/dashboards` (list of `{id, name, dataset}`, `name` = `metadata.name`), `GET /api/dashboards/{id}`, `GET /api/alerting/check-rules` (empty).

| Asset | Request | Response | Id | Read-back |
|---|---|---|---|---|
| Dashboard `demo-postgres-metrics` ("demo-Postgres - Metrics", P1 golden, 4 `TimeSeriesChart` panels) | `POST /api/import/dashboard?dataset=default` | 200, the stored dashboard (`kind`, `metadata`, `spec`) with **no id anywhere** and no `Location` header | `eebfaf39-969d-4fe3-b379-9234d77e1937`, found only by listing | `GET /api/dashboards/{id}` 200; `spec` byte-equal to what was sent |
| Check rule `demo-[Postgres] Number of connections … {{host.name}}`, `enabled: false` | `POST /api/import/check-rule?dataset=default` | 200, the rule with `id` | `987f6f55-cda3-4afe-b742-71d68b42e267` at `id` | `GET /api/alerting/check-rules/{id}` 200; read-back has no `id` field |

Findings:

- **Dashboard id:** the old `DASHBOARD_ID_PATH = metadata.dash0Extensions.id` was wrong; every dashboard import would have been `unknown`. Fixed on `48-dash0-client`: `publish_dashboard` lists before and after the import and takes the one new id with the dashboard's `metadata.name` (exactly one, else `unknown`).
- **`metadata.project`** is accepted: `datadog-migration` is kept, and Dash0 files the dashboard in folder `/datadog-migration` (annotation `dash0.com/folder-path`). Dash0 adds `labels: {dash0.com/source: ui}`, `dash0Extensions: {dataset}`, `version: 1` and timestamps.
- **Check rule normalization:** `interval` `1m` → `1m0s`; defaults added: `keep_firing_for: 0s`, `dataset`, `metadata.labels`. `name`, `expression` (with `[15m:1m]` and `$__threshold`), `thresholds`, `for`, `annotations` and `enabled: false` come back unchanged. The `{{host.name}}` in the name is stored verbatim; whether it is rendered can only be seen once the rule evaluates.
- **Panel kinds** seen in existing UI dashboards: `Markdown`, `PieChart`, `StatChart`, `TimeSeriesChart` (Grid layout, `PrometheusTimeSeriesQuery`), so `StatChart` and `Markdown` from plan 05 are known kinds. Not yet checked visually: that the imported panels render with data, and `ListVariable`.
- **Cleanup (user-approved, 2026-11-07 20:08 UTC):** `DELETE /api/dashboards/{id}` and `DELETE /api/alerting/check-rules/{id}` (with `?dataset=default`) both returned 200. Deletion is soft: a GET by id still returns 200 with the annotation `dash0.com/deleted-at`, but both list endpoints leave the assets out (dashboards back to the two `telemetry-inventory-*`, check rules back to 0). So the before/after listing in `publish_dashboard` doesn't see deleted dashboards.

## Handoff entry template

Post this as a comment on the issue at a meaningful handoff. Update the current-state table above only when the overall state changes, rather than leaving contradictory entries.

```text
Time / contributor:
Task and files owned:
Completed behavior:
Checks run and actual results:
Live evidence, if any (sanitized IDs/links or private evidence location):
Contract changes / decisions:
Remaining blockers:
Next concrete task:
Ownership released or retained:
```
