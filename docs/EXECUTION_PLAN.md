# MVP execution plan

> **Superseded where it conflicts (2026-11-07):** the implementation plan is now [`docs/handoff/`](handoff/README.md). Where this document disagrees with it (first example, command names, priorities, phases), the handoff directory wins. This file stays as background.

**Before anything else, enforce deterministic conversion. No LLM shall be involved in source-to-Perses translation or related query/alert conversion, including optional repair or fallback paths.** Establish the explicit parser/mapping/rule contract before feature work. Every milestone is subordinate to this rule; cut features before relaxing it.

Work in order. Choose one driver per task and keep ownership in [STATUS.md](STATUS.md). Drivers can be a human, Codex, or Claude; module names stay independent of the tool. This plan does not request parallel agents.

The hackathon duration is not specified. Allocate the remaining engineering time proportionally: roughly 15% setup and destination proof, 45% the complete migration slice, 20% hardening, and 20% demo/reproduction/submission. These are planning limits, not measured estimates. Reduce feature breadth when behind; preserve the live end-to-end check and final demo buffer.

## 0. Unblock the repository and destination

**Do this first; destination/schema surprises must be found early.**

- Inspect the current branch/worktree and read the shared instructions.
- Resolve the challenge's requirement to start from `vimouzin/dash0-dashboard-migrator`, fork it, and submit a PR against its `main` branch. The current `XNotAGuestX/thinchackdash` remote is not proof of that relationship.
- Prefer working in a clone of the required fork and copying these handoff files there. Alternatively, establish upstream ancestry deliberately after inspecting history. Do not overwrite this repository's remote or force an unrelated-history merge without a deliberate team decision.
- Create a feature branch before implementation commits. A `codex/` branch prefix is a tooling convention, not an agent-specific architecture choice.
- Prepare EU accounts, an organization starting with `thinc`, Datadog API/application keys, and a Dash0 token scoped to the demo dataset. Keep secrets local.
- Export a known-good simple Dash0 timeseries dashboard and a disabled check rule. Inspect exact plugin identifiers, query structure, datasource references, IDs, and units.
- With live work authorized, test the official import/read-back path using minimal valid assets in the demo dataset. Save sanitized contract fixtures and record the actual schema/source URL.
- Choose one gauge and verify its name/labels/unit in the destination. Arrange controlled telemetry early; prefer an existing demo feed or a tiny emitter over new infrastructure.

**Gate:** repository/submission route is understood, the destination payload contract is known, and the telemetry/demo prerequisite is working or clearly owned. If credentials are delayed, continue offline work while recording this as an unresolved P0 blocker.

## 1. Bootstrap the smallest executable slice

- Initialize one Python 3.13 CLI package with uv (`pyproject.toml`, committed `uv.lock`) and the proposed dependencies.
- Define the `SourceProvider` interface, shared output types, and static provider table with Datadog as the only entry. Make `--source` required for `fetch` and `compile`; see [the handoff](PROJECT_HANDOFF.md#source-provider-interface).
- Add `dev`, `build`, `typecheck`, and `test` scripts; document the exact working commands and tested runtime in README.
- Add synthetic dashboard, monitor, and mapping JSON fixtures matching the first supported example.
- Add the minimum types and pydantic boundary models needed for those fixtures.
- Wire `compile` through the selected provider so it reads fixtures, emits one dashboard/check-rule artifact plus a report/manifest, and never calls a network service.

**Gate:** a fresh install can run the offline command and produce reviewable outputs. At this stage, hard-coded example output is only scaffolding; it does not satisfy the translation gate.

## 2. Implement deterministic translation

- Tokenize and fully parse the bounded grammar; reject trailing input and unknown constructs.
- Load and validate explicit gauge/label/unit mappings.
- Compile the simple chart query and rolling-window monitor into PromQL.
- Emit a real Perses chart using the verified Dash0 example; emit a disabled check-rule API payload.
- Add focused tests for successful compilation, exact filters/escaping, missing mappings, unsupported functions, threshold mismatch, and lookback versus pending duration.
- Account for every item in the report, including partial dashboards and blocked monitors.

**Gate:** fixture input, parser model, mapping, PromQL, output JSON, and diagnostics can be inspected end to end. Repeating compilation produces the same semantic artifacts.

## 3. Complete the live vertical slice

- Implement selected Datadog dashboard/monitor fetching with the right site and key headers. Preserve the fetched JSON without converting it in the reader.
- Implement manifest validation and `import --dry-run` before destination writes.
- Import eligible artifacts with explicit host/dataset selection; retain returned IDs and per-asset outcomes.
- Read back the created resources using documented destination APIs, then inspect the rendered UI.
- Query actual telemetry and verify the monitor condition using controlled low/high values. Document sampling/timing differences and manual steps.
- Handle a repeated unchanged import through local receipts. Treat ambiguous timeouts as unknown until reconciled.

**Gate:** one fetched Datadog dashboard and monitor have real destination IDs, a working chart, a verified check condition, and recorded evidence. This is the first MVP-complete point, subject to the final checks below.

## 4. Harden what the demo depends on

Cover these behaviors with focused tests and one CLI smoke run:

| Area | Required check |
| --- | --- |
| First-priority invariant | Conversion uses only explicit parsers, reviewed mappings, and deterministic rules; identical inputs/configuration/version yield identical outputs; no model-based conversion, repair, or fallback path exists |
| Provider selection | Unknown `--source` exits `1` and lists known IDs; provider ID recorded in report and manifest; shared modules import no provider internals |
| Parser | Complete input consumption; unsupported syntax rejected |
| Mapping | Missing metric/tag, wrong type/unit, unsupported scale |
| Monitor | Correct window/threshold; unsupported behavior blocks import |
| Widgets | Unsupported widget/query reported; zero usable panels blocks dashboard |
| Output | Known-good schema shape and stable artifacts |
| Import | Correct auth/dataset and body; malformed artifact rejected before POST |
| Failure | 401/403, invalid request, one asset fails after another succeeds |
| Retry | Timeout yields unknown; no blind second POST |
| Receipt | Same artifact/destination skipped; changed artifact not silently overwritten |
| Reporting | Coverage and import status separate; exit codes reflect partial/failure |

Use HTTP mocks for contract/failure tests and real imports for live evidence. A PromQL parser or `promtool` can add syntax checks when available; do not call string checks a PromQL validator. `promtool` does not validate Dash0-specific JSON or query extensions.

**Gate:** relevant tests, type check, build, offline smoke run, and live evidence pass. List unverified semantic behaviors honestly.

## 5. Freeze, rehearse, and submit

- Stop adding features before the final 20% of the available time.
- Follow [DEMO.md](DEMO.md); rehearse the same fixtures and dataset that will be shown.
- Replace proposed CLI examples in README with tested usage and setup instructions. Explain exact supported/unsupported cases and credential requirements.
- Capture sanitized source/target evidence and a technical demo fallback. Do not commit live exports or credentials.
- Verify required starter ancestry and feature branch, then prepare the upstream PR with setup, features, validation, and limitations. Push/open it only when requested as part of submission.
- Update status with actual outcomes and outstanding blockers.

## Cut order when time is tight

1. Cut extra vendors, frontend, YAML, and broad source discovery.
2. Cut query-value widgets, formulas, exact styling/layout, and variable support.
3. Cut counters, warning thresholds, notification routing, and wider monitor semantics.
4. Keep one mapped gauge, one chart, one simple monitor, explicit incompatibility reporting, API fetch, and real Dash0 import. Keep the `SourceProvider` interface too, since it costs little; cut a second provider instead.

If live access is still blocked at the deadline, deliver the offline compiler, artifacts, tests, and exact reproduction/blocker details. State that the challenge's live end-to-end requirement remains unmet; do not present a fallback as completed acceptance.

## Copyable implementation kickoff

Use this with either Codex or Claude when starting implementation:

```text
Read AGENTS.md and follow its rules, then read docs/PROJECT_HANDOFF.md,
docs/STATUS.md, and docs/EXECUTION_PLAN.md. Both Codex and Claude may work
here; use shared, tool-neutral names and respect recorded file ownership.

Before anything else, enforce deterministic conversion. No LLM may participate
in source-to-Perses translation or related query/alert conversion, even as an
optional repair or fallback. Codex and Claude may write code and tests only;
they must not translate migration inputs as a step in the migration workflow.
Reduce scope before compromising this requirement.

Implement the next unfinished P0 milestone. Inspect the repository first,
resolve the required starter/fork route, and preserve existing work.
Prioritize one real dashboard and one real monitor migrated end to end.
Keep translation deterministic, report unsupported behavior, and leave
business work out of scope. Do not add stretch features before P0 works.

Update README with commands only after testing them. At handoff, update
docs/STATUS.md with completed behavior, exact check results, unresolved
blockers, file ownership, and the next concrete task. Distinguish offline,
mocked, and live evidence. If live access is unavailable, finish independent
offline work and record the missing end-to-end evidence accurately.
```
