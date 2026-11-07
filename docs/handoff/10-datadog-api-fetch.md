# 10 — Datadog API fetch by ID: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fetch --source datadog --dashboard-id <id>... --monitor-id <id>... --out <dir>` downloads the selected Datadog assets unchanged, into a folder that `convert --input <dir>` reads through exactly the same path as files.

**Architecture:**

- `SourceProvider` gains an optional `fetch`.
- The Datadog implementation does read-only GETs and writes the raw response text.
- No translation happens during fetch. API and file inputs meet at `collectInputFiles`.

**Tech Stack:** TypeScript, built-in `fetch`, vitest (with mocked fetch).

**Spec:** [00-context.md](00-context.md) §2 and §6; `docs/SOURCES.md` (Datadog API references).

**Depends on:** plan 01 for the client (Task 1). The round-trip test (Task 2) also needs plan 04's golden and the frozen mapping from plan 05 Task 0. Otherwise it runs independently of plans 02–09.

**Blocked by:**

- open blocker **B3**: a Datadog EU account with an API key and an application key (`DD_SITE`, `DD_API_KEY`, `DD_APP_KEY`);
- source assets that exist in that org.

Creating demo copies of the integrations-core assets in Datadog is a write to the source vendor. It needs the user's explicit go-ahead.

## Global Constraints

- The base URL is `https://api.<DD_SITE>`, defaulting to `datadoghq.eu`. The headers are `DD-API-KEY` and `DD-APPLICATION-KEY`. Never print them.
- Endpoints: `GET /api/v1/dashboard/{id}` and `GET /api/v1/monitor/{id}`. IDs are validated against `^[A-Za-z0-9-]+$` before any request.
- Output: `<out>/dashboards/<id>.json` and `<out>/monitors/<id>.json`, containing the exact response bytes. `--out` must be empty.
- Exit codes: `0` when every asset was fetched, `1` on the first error. The error message has the status code and a body cut to 500 characters, with no key values.

## Review Focus

1. **An ID containing `../`:** reject it before any request or file write. Covered by `rejects unsafe ids` (Task 1).
2. **A 403 caused by an application key without read scope:** the message names the missing permission class, not the key. Covered by `403 explains scope` (Task 1).
3. **The fetched monitor JSON is the API shape** (not wrapped): `recognizeAssets` (plan 01) already accepts the raw monitor shape. Covered by `fetched folder converts` (Task 2).
4. **Pagination and broad discovery:** out of scope, because only explicit IDs are fetched. No test.
5. **Repeated fetches of the same ID into a non-empty `--out`:** refused. Covered by `refuses non-empty out` (Task 1).

---

### Task 1: The Datadog fetch client

**Files:**
- Create: `src/source/datadog/api.ts`
- Modify: `src/source/provider.ts` (optional `fetch`)
- Test: `tests/datadog/api.test.ts`

**Interfaces:**
- Produces:
  - `export interface FetchSelection { dashboardIds: string[]; monitorIds: string[] }`
  - `export function fetchDatadogAssets(sel: FetchSelection, env: Record<string, string | undefined>, out: string, fetchImpl?: typeof fetch): Promise<{ written: string[] }>`
  - `SourceProvider.fetch?` delegates to it.

- [ ] **Step 1: Write the failing tests**, using a mock fetch.
  - `fetches by id with headers`: assert the URL `https://api.datadoghq.eu/api/v1/dashboard/abc-123` and both headers.
  - `writes exact bytes`.
  - `rejects unsafe ids`.
  - `403 explains scope`: the message matches `/application key lacks read access/`.
  - `refuses non-empty out`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 2: CLI and round trip

**Files:**
- Modify: `src/cli.ts`
- Test: `tests/fetch-convert.test.ts`

- [ ] **Step 1: Write `fetched folder converts`.**
  - The mock fetch returns the pinned "Postgres - Metrics" JSON and the **inner** `definition` of `percent_usage_connections` (the API shape).
  - Run `convert` on that folder with `fixtures/mappings/postgres-p0.json`.
  - The dashboard artifact is byte-equal to `fixtures/expected/postgres-p0/dashboards/postgres-metrics.json`.
- [ ] **Step 2: Wire the `fetch` command.** Run `npm test && npm run typecheck`; both must pass. Commit.
- [ ] **Step 3: Live run** (with credentials and the user's go-ahead). Fetch one real dashboard and one real monitor, convert them, and record the selected IDs and the sanitized shapes in `docs/STATUS.md`.
