# Shared project status

Last updated: 2026-11-07, planning handoff ([PLANNING_HANDOFF.md](PLANNING_HANDOFF.md)).

Highest-priority requirement: deterministic conversion before all other objectives. No LLM involvement in source-to-Perses or query/alert conversion, including optional inference, repair, and fallback paths. Shared rules, handoff, kickoff prompt, and acceptance gates now state this explicitly. Codex and Claude remain implementation assistants only.

## Actual state

| Area | State | Evidence |
| --- | --- | --- |
| Project scope and handoff | Written | `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, `DEMO.md` |
| Planning for the Postgres golden case and service order | In progress, blocked on the Dash0 inventory | [`PLANNING_HANDOFF.md`](PLANNING_HANDOFF.md): user decisions, research, open decisions, draft M0–M4 plan |
| Shared Codex/Claude rules | Written | Root `AGENTS.md`; `CLAUDE.md` refers to it |
| Local configuration template | Written | Root `.env.example` and `.gitignore` |
| Starter/fork relationship | Unresolved | Current remote is `XNotAGuestX/thinchackdash`; required starter differs |
| CLI/runtime/package | Not started | No implementation files or package manifest |
| Fixtures/parser/compiler | Not started | Paths and contracts are proposed only |
| Datadog API integration | Not started | No credentials or live source evidence checked |
| Dash0 API/schema spike | Docs researched | API, PromQL naming, and CLI facts in `PLANNING_HANDOFF.md` §5.3; no live request made |
| Telemetry and semantic validation | Not started | No dataset or demo feed verified |
| Automated checks | Not available | No application tests/build exist yet |
| Submission | Not started | No commit, push, fork, or PR created by the handoff task |

Handoff verification: all eight Markdown files passed local link, heading-anchor, and code-fence checks. Git ignore checks confirmed that `.env`, `.env.local`, run artifacts, and private inputs are excluded. These are documentation/configuration checks, not application or live migration tests.

## Current ownership

No implementation task is claimed. Codex and Claude must read this file before editing and record task-based ownership here when sharing active work. Avoid concurrent edits to the same files.

| Task | Driver | Files | Dependencies / next handoff |
| --- | --- | --- | --- |
| Next: Dash0 inventory (M0), then finalize the plan | Unclaimed | `docs/STATUS.md`, `docs/PLANNING_HANDOFF.md` | Needs Dash0 data access; see `PLANNING_HANDOFF.md` §4 and §10 |

## Next concrete action

Follow [`PLANNING_HANDOFF.md`](PLANNING_HANDOFF.md) §10:

1. Run the read-only inventory of the default Dash0 dataset (M0), and record a sanitized summary here.
2. Order the services by the data found.
3. Ask the user the three open decisions (§7: target metric names given the semconv gap, alert file format, monitor strictness).
4. Finalize the development plan and update `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, and `DEMO.md`.

The starter/fork workflow is still unresolved; settle it before the first implementation commit.

## Recorded decisions

- 2026-11-07 (user): translation does not need to be source-agnostic. Datadog is the only P0 source. Each source provider owns its parsing, mapping, and translation; the requirement is one `SourceProvider` interface with a static table selected by `--source`, plus shared output types (Perses dashboards, PromQL check conditions, diagnostics, outcomes). If a shared contract would limit Datadog functionality, discuss it with the user before compromising features. Contract: `PROJECT_HANDOFF.md`, section "Source provider interface".

## Known blockers and decisions to resolve

- No hackathon deadline or engineering time budget was supplied; use the proportional plan and record the actual deadline when known.
- Account/token availability, destination dataset, and actual target metric/labels are unknown.
- Dash0 data access (2026-11-07): the user-scope `dash0` MCP server (`https://api.eu-west-1.aws.dash0.com/mcp`) is authenticated and shows Connected, but its tools did not load into the planning session, including after resume. A brand-new session should load them. There is no `.env` or `DASH0_*` variable, and the `dash0` CLI is not installed. Datadog credentials are unset; they're not needed for offline work with integrations-core assets.
- OTel semconv defines only client-side PostgreSQL telemetry, so server metrics need another target source (decision open, `PLANNING_HANDOFF.md` §7.1).
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
