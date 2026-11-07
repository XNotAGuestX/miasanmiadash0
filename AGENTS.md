# Shared agent rules

## Highest priority: deterministic conversion

**Deterministic conversion is of utmost importance and comes before every other project objective, including MVP speed, feature coverage, and demo polish. No LLM shall be involved in translation from any source to Perses.** This also applies to query translation into PromQL and alert translation into Dash0 check rules.

The entire conversion path must use explicit parsers, reviewed mapping tables, deterministic rules, and schema validation. No local or hosted model, model-based mapping inference, agent call, optional AI mode, repair step, or LLM fallback may participate. Unsupported or ambiguous input must produce a diagnostic and be blocked from automatic conversion; never ask a model to fill the gap. With the same input, mapping, configuration, and compiler version, conversion must produce the same target artifacts and diagnostics.

Codex and Claude may help develop code and tests. They must not translate migration inputs or generate target assets as a step in the migration workflow. Reduce scope before compromising this requirement.

These rules apply to all contributors and coding agents, including **Codex and Claude**. This is the canonical project instruction file. Keep shared rules here; tool-specific entry files must refer here instead of maintaining competing copies. Explicit user instructions take precedence over project defaults.

## Read first

1. This file.
2. `docs/handoff/README.md`, the implementation plan: which handoff holds what, the order, and the open decisions. Then `docs/handoff/00-context.md` (the shared spec) and the plan you're taking.
3. `docs/STATUS.md` for actual progress and current ownership.
4. `docs/PROJECT_HANDOFF.md` and `docs/EXECUTION_PLAN.md` for background. Where they conflict with `docs/handoff/`, the handoff directory wins.

Read existing code before changing it. The handoff describes planned behavior; source code, executable checks, and recorded live evidence establish what works today.

## Objective and scope

- Ship the smallest working Datadog → Dash0 migration: one dashboard, one metric monitor, deterministic translation, report, and actual destination import.
- Time is limited. Finish the vertical slice before adding more query functions, widget types, or vendors.
- Business work is handled separately. Do not spend implementation time on market research, pricing, ROI models, pitch decks, branding exercises, or a marketing website.
- Do not build a frontend, database, job queue, plugin framework, Kubernetes deployment, or cloud infrastructure for the MVP.
- Codex and Claude are development tools. No LLM involvement is permitted anywhere in the conversion workflow, even as an optional dependency or fallback.

## Implementation rules

- Use neutral names such as `source`, `parser`, `compiler`, `mapping`, `destination`, and `report`. Avoid agent-specific modules or permanently assigning a subsystem to a tool.
- Prefer one package, pure translation functions, explicit data types, and a small number of modules.
- Select the source vendor through the single `SourceProvider` interface and static provider table (`--source datadog`); see the handoff's source provider interface section. Each provider owns its source-specific parsing, mapping, and translation; a vendor-neutral intermediate model is not required. Keep shared CLI, report, manifest, validation, and destination code free of source-specific logic. The static table is not a plugin framework: no dynamic loading, discovery, or config-driven registration.
- Keep network I/O out of the parser/compiler. Offline compilation must work without credentials.
- Parse the documented query subset completely. Never translate a recognized prefix and ignore trailing syntax. Regex may tokenize a bounded grammar; chained string replacements are not a semantic parser.
- Unknown metric types, units, label mappings, options, or functions require a diagnostic. Do not infer telemetry equivalence from similar names or replace dots with underscores as a migration strategy.
- Preserve original source assets and source locations. Report each omitted widget, query, and behavior. An alert with unsupported semantics is blocked from import.
- Separate syntax/schema validation, API acceptance, and observed semantic validation in the report. None proves the others.
- Keep output deterministic, with stable asset ordering and repeatable names. Isolate timestamps and API responses from compilation snapshots.
- Validate actual Dash0 request bodies against official documentation and a known-good export. Do not invent a schema, endpoint, plugin identifier, or response ID path.
- Keep patches focused. Do not refactor unrelated work or add stretch features while a P0 milestone is unfinished.

## Working together

- Both Codex and Claude may work in this repository. Before editing, inspect the worktree and read current ownership in `docs/STATUS.md`.
- Use task-based ownership: state the goal, files being changed, interface dependencies, and next handoff. Avoid simultaneous edits to shared contracts, package manifests, lockfiles, and the same source files.
- Do not overwrite, discard, stash, reset, or clean another contributor's changes. Coordinate when ownership overlaps.
- Agree on interface changes before making dependent edits. Update the handoff and consumers together when a contract changes.
- Parallel agent work is optional and only used when explicitly requested. This handoff does not itself authorize spawning agents.
- At handoff, update `docs/STATUS.md` with completed work, exact checks and results, remaining blockers, and the next concrete task. Record facts, not assumed completion.
- Do not commit directly to `main`. Follow the challenge's fork → feature branch → upstream PR workflow. Do not push or open a PR merely because this document describes submission.

## Credentials and live operations

- Read credentials from environment variables; keep `.env`, private exports, raw live responses, and run artifacts out of Git.
- Never print keys, tokens, authorization headers, or full environment dumps. Redact sensitive response content in reports.
- `compile` is offline and read-only with respect to vendors. `fetch` reads selected source assets. Only an explicit `import` command writes to the selected Dash0 dataset.
- Use a demo dataset and demo-prefixed names. Default imported checks to disabled; enable the specific demo check only as part of an explicitly requested live verification.
- Do not modify or delete source assets. Do not overwrite destination assets by name. Use recorded destination IDs only for an explicit, documented update flow after the MVP.
- Do not blindly retry a creation request after an ambiguous timeout; reconcile the result before creating again.
- Do not repeatedly request permission for ordinary local implementation and tests already requested by the user. Creating this handoff does not authorize live account changes or sending messages to others.

## Verification and completion

- Add focused behavioral tests for translation semantics, unsupported constructs, schemas, and import failure handling. Use synthetic or sanitized fixtures.
- Run the relevant tests and type checks for the change. Once they pass, move on unless a new issue warrants more checking.
- Never claim a live migration from mocks or a screenshot of generated JSON. Record returned IDs and read-back/UI evidence.
- Never describe an API-accepted empty dashboard as a successful functional migration. Demonstrate data and a check condition, or clearly record missing runtime evidence.
- If access is blocked, keep completing offline work and record the blocker. Do not mark the end-to-end milestone complete.
- Report what changed, what was checked, limitations, and the next step briefly. Do not invent test results.
