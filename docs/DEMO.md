# Technical demo and acceptance runbook

**First acceptance gate: conversion is fully deterministic, with no LLM involved in source-to-Perses or query/alert translation.** Optional model-based conversion, repair, and fallback paths also fail this gate. Demo speed or appearance cannot override it.

This is a planned runbook. No commands or live migrations have been implemented or executed yet. Replace the proposed commands with tested ones during implementation.

## Prepare once

- Use a dedicated demo dataset and demo-prefixed resource names.
- Have one Datadog dashboard with a supported timeseries widget and one metric monitor matching the supported grammar.
- Keep a separate incompatibility fixture with an unsupported function/widget so it cannot disrupt the clean happy-path import.
- Keep the mapping file explicit: actual target metric, gauge type, matching units, and exact label mapping.
- Confirm the target dataset contains the demo telemetry. Prefer a small controlled feed with values below and above the chosen threshold. If possible, feed the same samples into both platforms.
- Store source exports, API responses, receipts, and screenshots locally under ignored directories. Sanitize anything shared in the PR.
- Ensure a known successful destination import is available before the live presentation. Reuse its receipt/read-back evidence rather than blindly recreating assets.

## Show the migration in about five minutes

1. **Show the source.** Open the selected Datadog dashboard and monitor. Point to one query, its lookback, critical threshold, and unit.
2. **Fetch and compile.** Run selected-ID fetching, then offline compilation. Show the original query, explicit mapping, generated PromQL, Perses payload, and check-rule payload.
3. **Show accountability.** Open the JSON/terminal report. Distinguish translated coverage from destination imports. Run the separate unsupported fixture and show the source path and suggested manual action.
4. **Import.** Show the dry-run plan with the target dataset, then explicitly import the clean bundle. Show the returned destination IDs or the receipt for an unchanged prior import.
5. **Verify in Dash0.** Open the actual destination dashboard and check rule. Show chart data and the check's query/window/threshold. Enable only the demo check as part of the requested demo, and show a controlled threshold crossing or previously captured verified evaluations if the lookback requires more time.
6. **State the boundary.** Name the supported subset and the remaining behaviors requiring manual review. Keep business messaging with the separate business owner.

Do not spend the presentation waiting for an entire five-minute window to elapse. Seed the series and capture evaluation evidence in advance; explain the timing. Never substitute generated JSON for a rendered destination dashboard.

## Reproduction sequence

Use the proposed CLI sequence in [the handoff](PROJECT_HANDOFF.md#cli-and-artifact-contract) until README contains executable setup/usage instructions. For offline review, the final project should provide:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run dev -- compile --source datadog --dashboard fixtures/datadog/dashboard.json --monitor fixtures/datadog/monitor.json --mapping fixtures/mappings/demo.json --out artifacts/review
```

These scripts and fixtures must be created and verified before this sequence is marked usable. The offline path must not need Datadog, Dash0, Codex, Claude, or model API credentials.

For the live path, document required environment variables, selected source IDs, the destination API host/dataset, and how to inspect returned assets. Keep secrets out of command arguments and examples. Use the fetched copies as compiler inputs; do not silently swap in pretranslated fixtures.

## Evidence to retain

| Acceptance claim | Required evidence |
| --- | --- |
| Real source ingestion | Selected IDs and sanitized fetched source shapes |
| Deterministic compilation | Reviewed expected outputs and repeated-run comparison |
| Correct supported query | Parsed structure, mapping, PromQL, focused tests |
| Functional destination dashboard | Returned ID/read-back plus chart showing actual telemetry |
| Functional destination check | Returned ID/read-back plus verified controlled evaluation |
| Transparent incompatibilities | Unsupported fixture, report diagnostic, import exclusion |
| Partial import handling | Per-asset result when one request fails; no all-success claim |
| Reproducibility | Exact runtime, commands, check results, and known limitations |

Separate evidence of syntax, schema, API acceptance, and runtime semantics. Record validation failures and untested cases explicitly. A dashboard/check existing in the UI proves import, but does not by itself prove preserved behavior.

## Fallback and cleanup

- If the live network fails, show previously verified destination assets/evidence and rerun the offline compiler. Label historical evidence clearly; do not claim the current live attempt succeeded.
- If no live import has ever succeeded, show the offline result and state that live acceptance remains incomplete.
- On an ambiguous creation timeout, inspect the dataset and reconcile IDs before retrying. Keep uncertain outcomes marked `unknown`.
- After the demo, disable only the check created for it if needed. Resource deletion is a separate explicit action; keep recorded IDs available for deliberate cleanup.

## Technical PR checklist

- [ ] Feature branch belongs to a fork of the required starter and targets upstream `main`.
- [ ] PR explains the supported end-to-end behavior and exact limitations.
- [ ] Setup, environment variables, offline examples, and live examples are tested.
- [ ] Deterministic parsing/mapping and unsupported-feature behavior are easy to inspect.
- [ ] Tests, type check, build, and live evidence are reported accurately.
- [ ] Private exports, real credentials, generated run artifacts, and model/runtime secrets are excluded.
- [ ] No LLM participates in conversion, including optional mapping inference, repair, or fallback paths; identical inputs/configuration/version produce identical target artifacts and diagnostics.
