# Shared project status

Last updated: 2026-11-07, about 14:50 UTC: Dash0 inventory (M0) done ([DASH0_INVENTORY.md](DASH0_INVENTORY.md)); planning handoff in [PLANNING_HANDOFF.md](PLANNING_HANDOFF.md).

Highest-priority requirement: deterministic conversion before all other objectives. No LLM involvement in source-to-Perses or query/alert conversion, including optional inference, repair, and fallback paths. Shared rules, handoff, kickoff prompt, and acceptance gates now state this explicitly. Codex and Claude remain implementation assistants only.

## Actual state

| Area | State | Evidence |
| --- | --- | --- |
| Project scope and handoff | Written | `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, `DEMO.md` |
| Planning for the Postgres golden case and service order | In progress: M0 done; waiting on the user's decisions (§7 items 1–5) | [`PLANNING_HANDOFF.md`](PLANNING_HANDOFF.md): user decisions, research, gaps (§8a), draft M0–M4 plan |
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
| Next: user decisions (§7 items 1–5), then finalize the plan and docs | Unclaimed | `docs/PROJECT_HANDOFF.md`, `docs/EXECUTION_PLAN.md`, `docs/DEMO.md`, `docs/STATUS.md` | Needs the user's answers; see `PLANNING_HANDOFF.md` §7 and §10 |

## Next concrete action

Follow [`PLANNING_HANDOFF.md`](PLANNING_HANDOFF.md) §10:

1. ~~Run the read-only Dash0 inventory (M0).~~ Done: [`DASH0_INVENTORY.md`](DASH0_INVENTORY.md).
2. ~~Order the services by the data found.~~ Done: Postgres → host → Kafka → Redis → Nginx → Docker.
3. Ask the user the open decisions (§7):
   1. target vocabulary;
   2. alert file format;
   3. monitor strictness;
   4. demo telemetry owner and connection-holder script;
   5. Dash0 token or UI export.
4. Finalize the development plan, update `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md` and `DEMO.md`, and start M1 (bootstrap).

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
