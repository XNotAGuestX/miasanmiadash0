# Datadog → Dash0 Migrator

**Highest priority, before anything else: deterministic conversion. No LLM shall be involved in translation from a source to Perses, PromQL, or Dash0 check rules—not even as an optional fallback. Reduce MVP scope before compromising this rule.** Codex and Claude may help write the implementation and tests; migration itself uses explicit parsers, mappings, and deterministic rules only.

Hackathon project: a deterministic CLI that migrates Datadog dashboards and metric monitors to Dash0 using Perses, PromQL, and explicit telemetry mappings.

**Current state: the offline `convert` command works for Datadog dashboards (Track A: query parser, mapping, PromQL, Perses dashboards) and metric monitors (Track B, plan 06). A supported monitor becomes `rules/<slug>.prometheus.{json,yaml}` (warning and critical rules) and `check-rules/<slug>.json` (a disabled, create-only Dash0 check-rule body), both rendered from one condition `<agg>_over_time((<query>)[<window>:1m])`; anything outside the reviewed allowlist is blocked with a diagnostic. `publish` and `fetch` don't exist yet.** See [STATUS.md](docs/STATUS.md).

## Install, test, convert

Everything runs through one entry point, `uv run migrator <command>`:

```bash
uv sync                      # install runtime and dev dependencies (Python ≥ 3.13)
uv run migrator test         # pytest; extra args pass through, e.g. `uv run migrator test -k parse`
uv run migrator typecheck    # mypy --strict over src and tests
uv run migrator lint         # ruff
uv run migrator check        # lint + typecheck + test
uv run migrator convert --source datadog \
  --input fixtures/datadog/integrations-core/postgres \
  --mapping mappings/datadog/postgres.json --out /tmp/pg-out   # --format yaml, --project <name>
```

`convert` is offline. It writes `dashboards/`, `source/` copies, `report.json` and `manifest.json` into an empty `--out` directory, and exits `0` (all translated), `2` (some item partial or blocked) or `1` (bad input, mapping or arguments).

## Start here

1. Read [AGENTS.md](AGENTS.md), the shared working rules for humans, Codex, and Claude.
2. Read [the implementation plan overview](docs/handoff/README.md): which handoff holds what, the order of work, and the open decisions. Each numbered file in `docs/handoff/` is a self-contained, test-first plan.
3. Background: [the project handoff](docs/PROJECT_HANDOFF.md) (scope, architecture, acceptance criteria) and [the execution plan](docs/EXECUTION_PLAN.md). Where they conflict with `docs/handoff/`, the handoff directory wins.
4. Check and update [STATUS.md](docs/STATUS.md) before handing work to another contributor.
5. Use [the demo runbook](docs/DEMO.md) to verify the deliverable.

[CLAUDE.md](CLAUDE.md) directs Claude to the same shared rules. Technical references and the challenge's submission requirements are collected in [SOURCES.md](docs/SOURCES.md).

## The first deliverable

Fetch one selected Datadog dashboard and one selected metric monitor, compile the supported subset, export reviewable artifacts and a migration report, import both into Dash0, and show the resulting dashboard and check rule in the Dash0 UI. Include an unsupported example that produces a useful diagnostic.

Build a working vertical slice before expanding feature coverage. Business research, pricing, positioning, and pitch work are handled separately.

## Implementation stack

- Python ≥ 3.13 with uv, one package (`src/migrator`), one console script (`migrator`).
- argparse for the CLI, pydantic (strict) for mapping and Perses schema validation, `promql-parser` for the PromQL syntax check, PyYAML for YAML output, pytest, mypy, ruff.
- Small deterministic parser and explicit mapping files for translation. The handoff's TypeScript names map one-to-one to Python modules (`parse-query.ts` → `parse_query.py`, and so on).
- One `SourceProvider` interface selected with `--source` (only `datadog` for now). Each provider owns its own translation; shared code handles the report, manifest, and Dash0 import.
- JSON inputs/outputs first. No frontend, database, or hosted service. LLM involvement in conversion is prohibited, not merely unnecessary.

These are starting decisions for the empty repository. Preserve any existing implementation if the handoff is moved into a populated starter checkout. Record a justified stack change once in the handoff and status file.

## Setup to complete during implementation

- Resolve the required starter/fork relationship before the first implementation commit; see [the execution plan](docs/EXECUTION_PLAN.md#0-unblock-the-repository-and-destination).
- Use a dedicated feature branch, for example `codex/mvp-migrator`; keep module names and task names tool-neutral.
- Create EU Datadog and Dash0 accounts. The challenge requires a Dash0 organization name beginning with `thinc`.
- Copy `.env.example` to `.env` and supply credentials locally. Implement explicit `.env` loading or document shell environment setup; the template alone does not load variables.
- Bootstrap the package and record working install/build/test/CLI commands here as soon as they exist.

No install or runtime command is advertised as working until it has been implemented and checked.
