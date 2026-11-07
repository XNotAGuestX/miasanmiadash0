# Shared project status

Last updated: 2026-11-07, initialization handoff.

Highest-priority requirement: deterministic conversion before all other objectives. No LLM involvement in source-to-Perses or query/alert conversion, including optional inference, repair, and fallback paths. Shared rules, handoff, kickoff prompt, and acceptance gates now state this explicitly. Codex and Claude remain implementation assistants only.

## Actual state

| Area | State | Evidence |
| --- | --- | --- |
| Project scope and handoff | Written | `PROJECT_HANDOFF.md`, `EXECUTION_PLAN.md`, `DEMO.md` |
| Shared Codex/Claude rules | Written | Root `AGENTS.md`; `CLAUDE.md` refers to it |
| Local configuration template | Written | Root `.env.example` and `.gitignore` |
| Starter/fork relationship | Unresolved | Current remote is `XNotAGuestX/thinchackdash`; required starter differs |
| CLI/runtime/package | Not started | No implementation files or package manifest |
| Fixtures/parser/compiler | Not started | Paths and contracts are proposed only |
| Datadog API integration | Not started | No credentials or live source evidence checked |
| Dash0 API/schema spike | Not started | Official docs reviewed; no live import performed |
| Telemetry and semantic validation | Not started | No dataset or demo feed verified |
| Automated checks | Not available | No application tests/build exist yet |
| Submission | Not started | No commit, push, fork, or PR created by the handoff task |

Handoff verification: all eight Markdown files passed local link, heading-anchor, and code-fence checks. Git ignore checks confirmed that `.env`, `.env.local`, run artifacts, and private inputs are excluded. These are documentation/configuration checks, not application or live migration tests.

## Current ownership

No implementation task is claimed. Codex and Claude must read this file before editing and record task-based ownership here when sharing active work. Avoid concurrent edits to the same files.

| Task | Driver | Files | Dependencies / next handoff |
| --- | --- | --- | --- |
| Next: repository + destination setup | Unclaimed | Setup records; then README and contract fixtures | Execution plan phase 0 |

## Next concrete action

Resolve the required starter/fork workflow and create a feature branch for implementation. Then verify a known-good Dash0 dashboard/check payload and bootstrap the offline slice. Account setup and target telemetry can be prepared by a human teammate while offline implementation progresses, if the team chooses to split the work.

## Known blockers and decisions to resolve

- No hackathon deadline or engineering time budget was supplied; use the proportional plan and record the actual deadline when known.
- Account/token availability, destination dataset, and actual target metric/labels are unknown.
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
