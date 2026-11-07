# Shared project status

Last updated: 2026-11-07: implementation plan written and split into handoffs in [`handoff/`](handoff/README.md). Dash0 inventory (M0) done ([DASH0_INVENTORY.md](DASH0_INVENTORY.md)).

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
| CLI/runtime/package | Not started | No implementation files or package manifest |
| Fixtures/parser/compiler | Not started | Paths and contracts are proposed only |
| Datadog API integration | Not started | No credentials or live source evidence checked |
| Dash0 API/schema spike | Docs researched | API, PromQL naming, and CLI facts in `PLANNING_HANDOFF.md` §5.3; no live request made |
| Telemetry and semantic validation | Data present, not durable | `default` has data since 2026-11-07 14:06 UTC from one `docker-desktop` host. Connection usage is about 0.08; no controlled threshold crossing exists yet |
| Automated checks | Not available | No application tests/build exist yet |
| Submission | Not started | No commit, push, fork, or PR created by the handoff task |

Handoff verification: all eight Markdown files passed local link, heading-anchor, and code-fence checks. Git ignore checks confirmed that `.env`, `.env.local`, run artifacts, and private inputs are excluded. These are documentation/configuration checks, not application or live migration tests.

## Current ownership

No implementation task is claimed. Codex and Claude must read this file before editing and record task-based ownership here when sharing active work. Avoid concurrent edits to the same files.

| Task | Driver | Files | Dependencies / next handoff |
| --- | --- | --- | --- |
| Oracle-backed pytest suite (TDD), branch `feature/oracle-tests` (uncommitted) | Claude (Agent0 answers done for all 9 dashboards; awaiting human review of `fixtures/expected/REVIEW.md`) | `pyproject.toml`, `src/converter/__init__.py`, `tests/**`, `fixtures/**`, `scripts/{extract_cases,render_oracle_prompt,build_expected,run_oracle}.py`, `docs/handoff/00-context.md` §4–§5 | Stack switched to Python/pytest (user decision 2026-11-07). See "Oracle test suite handoff" below |
| Next: plan 01, bootstrap and `convert` CLI | Unclaimed | See [`handoff/01-bootstrap-cli.md`](handoff/01-bootstrap-cli.md) | None; runs offline. Then plans 02 → 03 → 04 (MVP converter) |

## Oracle test suite handoff (2026-11-07, Claude)

- **Setup (uv, 2026-11-07):** `uv sync` (uv-managed CPython 3.11 from `.python-version`, deps from `uv.lock`, groups `dev` + `oracle` by default). Run `uv run pytest` (unreviewed cases skipped) or `--include-unreviewed`. pip/venv setup is retired. Full guide: [`tests/README.md`](../tests/README.md).
- **Pipeline:** `scripts/extract_cases.py` (pinned dashboards → `fixtures/cases/`) → `scripts/render_oracle_prompt.py <svc>/<id>` (fixed template `fixtures/oracle/PROMPT.md` → `prompt.md`) → ask Agent0 → save verbatim `fixtures/oracle/agent0/<svc>/<id>/answer.yaml` → `scripts/build_expected.py <svc>/<id>` (rules overlay → `fixtures/expected/<svc>/<id>/expected.yaml`). Human decisions go in `overrides.yaml` next to it.
- **Agent0 done, all 9 dashboards** (answer + expected built): `postgres/postgresql_dashboard`, `postgres/postgresql_screenboard_dashboard`, `nginx/NGINX-Metrics_dashboard` (Dash0 UI chat); `nginx/NGINX-Overview_dashboard`, `nginx/plus_overview`, `redisdb/overview`, `docker_daemon/docker_dashboard`, `kafka/kafka_dashboard`, `kafka/kafka_kraft_dashboard` (dash0 MCP `runTask`, ~17:43–17:45 local, thread links in each `answer.yaml` header). No YAML quoting fixes were needed for the six MCP answers; every prompt `source_path` is answered.
- **Expected outcomes (unreviewed):** 69/207 requests translated, 98/251 leaf widgets translated, all 9 dashboards `partial`. Per dashboard (requests translated/total): Postgres Metrics 13/15, Postgres Overview 11/29, NGINX Metrics 6/7, NGINX Overview 7/9, NGINX Plus 5/22, Redis 18/29, Docker 6/20, Kafka 1/35, Kafka KRaft 2/41.
- **Function rule (2026-11-07, Claude, user-approved):** `scripts/build_expected.py` now blocks every request that uses a Datadog function (`ALLOWED_FUNCTIONS` is empty), matching plans 02/03/05. That flipped 20 Agent0 translations to blocked (`weighted` 9, `as_count` 4, `top` 2, `per_second` 2, `rollup`/`per_minute`/`diff`/`abs` 1 each), each with an overlay note keeping Agent0's PromQL. `fixtures/oracle/PROMPT.md` gained a "Hard rules" block (functions, no extra constants, only `$__rate_interval`, `rate()` only on monotonic sums, derived metrics and grain go in `notes`, prefixed variables → `=~"$name"`). The 9 recorded `prompt.md`/answers are unchanged (state hashes still match the old template); a default `run_oracle.py` run only warns that prompts changed. Use `--full` to ask Agent0 again with the new rules.
- **Checks (2026-11-07):** `.venv/bin/pytest -q --include-unreviewed` → 963 collected, 0 collection errors, **963 failed**, all with `ModuleNotFoundError: No module named 'converter.source'` (expected red; no engine yet). By file: `test_parse_query.py` 262, `test_request.py` 414 (207 × 2), `test_widget.py` 251, `test_dashboards.py` 36 (9 × 4). By milestone: p0 265, p1 44, p2 654. Default `.venv/bin/pytest -q` → 262 failed (parser cases, not oracle-gated), 701 skipped (unreviewed).
- **Docs:** [`fixtures/expected/REVIEW.md`](../fixtures/expected/REVIEW.md) (per-dashboard tables + flagged deviations), [`tests/README.md`](../tests/README.md), `handoff/00-context.md` §4/§5 now Python/pytest (with a TS → Python name table for plans 01–10).
- **Data caveat:** receiver data in `default` only exists 2026-11-07 ~14:05–15:21 UTC (OTel demo stopped). Live checks used that window. Not in the dataset at all: MySQL, MongoDB, Elasticsearch, Kubernetes.
- **Known deviations to review** (details in REVIEW.md "Decide these first"): no dedup grain on `postgresql.connections` (plan 05 wants one); CPU via `rate(system.cpu.time)` instead of `system.cpu.utilization` × 100; Agent0-added scaling constants (`100 *`, `/ 1e7`); translated Datadog functions `as_count`, `rollup(max)`, `per_second`, `per_minute`, `diff`, `top`, dropped `.weighted()`, `abs`; derived metrics (NGINX dropped = accepted − handled, Plus active = active − waiting); Redis expired vs evicted inconsistency; Kafka JMX `.rate` → `rate()`; hard-coded 15m window in NGINX Overview.
- **Remaining blockers:** (1) human review of REVIEW.md → `overrides.yaml` with `reviewed: true`; until then 701 oracle cases stay skipped. (2) `mappings/datadog/<service>.json` referenced by every `expected.yaml` does not exist yet (plans 03/05/08). (3) `converter.source.datadog` not implemented (plans 01–04). (4) user decision on adding MySQL/MongoDB/Elasticsearch/Kubernetes data.
- **Batch oracle runner (2026-11-07, Claude):** `scripts/run_oracle.py [fixtures/oracle/dashboards.json] [-j N] [--retries N] [--full] [--case SVC/ID] [--adopt-existing] [--dry-run]`. Input JSON lists the dashboards (`{"dataset", "model_class", "reasoning_effort", "dashboards": [{"case": "<svc>/<id>"}]}`). It runs N dashboards in parallel against the dash0 MCP server (`runTask` → `waitForTask`), validates each YAML answer against the case (every `source_path` answered, PromQL count = formula count), writes `prompt.md` + verbatim `answer.yaml`, then rebuilds `expected.yaml`. Progress is tracked in `fixtures/oracle/agent0/state.json` (status, thread ID, prompt sha256, attempts, last error). A default run asks only for cases that are not `done` and resumes `pending` threads; `--full` asks again for all. Retries use exponential backoff: a transport error retries the same thread, an invalid answer opens a new thread. State is seeded with all 9 existing answers (`--adopt-existing`); the recorded prompts match the current template. Run with `uv run scripts/run_oracle.py`; needs the `oracle` group (`mcp==2.3.0`, installed by `uv sync`) and `DASH0_AUTH_TOKEN` (read access) in the environment or `.env`. Checks: `uv run pytest -q tests/scripts` → 29 passed (fake Agent0 plus an in-process MCP server through the real SDK). **Not yet run live:** no token is available, so the HTTP/auth path to Dash0 is untested. `scripts/build_expected.py` gained a `write(key)` helper (same output).
- **Next:** user reviews REVIEW.md; then plan 01 → 04 against `tests/unit/requests` (p0 first: `uv run pytest -m p0`).

## Next concrete action

Follow [`handoff/README.md`](handoff/README.md):

1. The user reviews the plans and confirms or changes the assumed defaults A1–A3 (target vocabulary, alert output, monitor strictness) and A4 (`convert` / `publish` command names).
2. Claim plan 01 here and execute plans 01 → 02 → 03 → 04 (the offline MVP converter). No credentials needed.
3. In parallel, resolve blockers B1 (Dash0 token), B2 (demo telemetry owner) and B3 (Datadog account, plan 10 only).

The starter/fork workflow is still unresolved; settle it before the first implementation commit.

## Recorded decisions

- 2026-11-07 (user): translation does not need to be source-agnostic. Datadog is the only P0 source. Each source provider owns its parsing, mapping, and translation; the requirement is one `SourceProvider` interface with a static table selected by `--source`, plus shared output types (Perses dashboards, PromQL check conditions, diagnostics, outcomes). If a shared contract would limit Datadog functionality, discuss it with the user before compromising features. Contract: `PROJECT_HANDOFF.md`, section "Source provider interface".

## Known blockers and decisions to resolve

- No hackathon deadline or engineering time budget was supplied; use the proportional plan and record the actual deadline when known.
- **Demo telemetry isn't durable** (M0). `default` data exists only while one machine (`docker-desktop`) runs the OTel Demo stack. It needs an owner or an always-on host.
- **No controlled threshold crossing.** Postgres connection usage is about 0.08, against thresholds of 0.8 and 0.9. It needs a connection-holder script; changing the thresholds isn't allowed.
- **Series deduplication.** Resource-hash churn after a collector restart makes `sum` double-count. The reviewed ratio must deduplicate (`PLANNING_HANDOFF.md` §6).
- **Dash0 token missing.** The `dash0` MCP tools load but are read-only: they can't export a dashboard, list or import check rules, or import anything. A `DASH0_AUTH_TOKEN` (or a manual UI export, for the emitter reference only) is needed. The `dash0` CLI isn't installed.
- **Datadog credentials unset.** P0 uses integrations-core files pinned to `a9b9e42b7e484861ecbd1f5919da7c52a694b74d`. API fetch stays at M4+.
- Target labels are settled by the data: postgresqlreceiver 0.160.0, legacy `postgresql_database_name` and `postgresql_table_name`. The user still needs to confirm this (`PLANNING_HANDOFF.md` §7.1).
- This branch is 2 `.gitignore` commits behind `main`. Reconcile it before implementation.
- Stack defaults are proposed for an empty repository; no package versions have been installed or tested.
- The official check-rule documentation has differing ID references in prose and schema; verify the actual request shape during the destination spike.

## Handoff entry template

Append a concise entry at a meaningful handoff; update the current-state table rather than leaving contradictory entries.

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
