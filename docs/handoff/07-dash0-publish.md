# 07 — Publish to Dash0 and verify: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `publish --from <dir> [--dry-run] [--allow-partial]` imports eligible converted dashboards and check rules into one Dash0 dataset. It's create-only, with local receipts and read-back, and every outcome is honest: `imported`, `failed` or `unknown`.

**Architecture:**

- `destination/dash0.ts` holds HTTP calls only; there's no translation logic in it.
- `publish` validates the manifest and artifact hashes before any write, then publishes sequentially in manifest order.
- Receipts prevent duplicates. An ambiguous timeout is recorded as `unknown` and never retried.

**Tech Stack:** TypeScript, built-in `fetch`, vitest (with mocked fetch).

**Spec:** [00-context.md](00-context.md) §2 (rules 5–6) and §7, plus the destination rules in `AGENTS.md` ("Credentials and live operations").

**Depends on:** plan 04 (dashboards) and plan 06 (check rules).

**Blocked by:**

- open blocker **B1**: a `DASH0_AUTH_TOKEN` scoped to dataset `default`;
- an explicit user go-ahead for each live write (Tasks 1 and 5).

Tasks 2–4 can be built offline with mocks.

## Global Constraints

- Configuration comes from `DASH0_API_URL`, `DASH0_AUTH_TOKEN` and `DASH0_DATASET` only.
  - Never print the token, the `Authorization` header or the full environment.
  - A missing variable gives `error: missing env: <NAMES>` and exit 1.
- Endpoints, each with `?dataset=<encoded>`:
  - `POST /api/import/dashboard`
  - `POST /api/import/check-rule`
  - `GET /api/dashboards/{id}`
  - `GET /api/alerting/check-rules/{id}`
- Create-only. Never send `metadata.dash0Extensions.id` or a check-rule `id`.
- The request timeout is 30 s. A timeout or network error after the request starts is `unknown`. There's no automatic retry.
- Stop the whole run on HTTP 401 or 403.
- Exit codes:
  - `0`: every selected artifact was imported or skipped as unchanged.
  - `2`: something was excluded (a partial without `--allow-partial`, or a blocked artifact).
  - `1`: any `failed` or `unknown` result, or a validation error.

## Review Focus

1. **A timeout after the POST was sent:** record `unknown`, and refuse to republish that artifact until a human reconciles it. Covered by `timeout yields unknown and blocks re-publish` (Task 3).
2. **A changed artifact whose old version was already imported:** refuse it, because there's no update flow. Covered by `changed artifact is rejected` (Task 3).
3. **A manifest entry pointing outside `--from`** (`../x.json`): reject it before any network call. Covered by `rejects paths outside the run dir` (Task 4).
4. **A 401 on the first asset:** stop; don't try the rest. Covered by `stops on auth failure` (Task 4).
5. **Error output when the token is wrong:** it contains no token. Covered by `never leaks the token` (Task 2).

---

### Task 1: Live contract check (manual; needs the token and the user's go-ahead)

**Files:**
- Create: `fixtures/dash0/contract/` (sanitized requests and responses)
- Create: `fixtures/dash0/dashboard-export.json`
- Modify: `docs/STATUS.md`

- [ ] **Step 1: Export a known-good dashboard (read-only).**
  - Run `GET /api/dashboards?dataset=default`, then `GET /api/dashboards/{id}` for `telemetry-inventory-overview`.
  - Save it sanitized to `fixtures/dash0/dashboard-export.json`. Remove any token and org ID, and replace timestamps with `"<redacted>"`.
  - Note which panel and variable kinds it uses.
- [ ] **Step 2: Import the P0 golden.** With the user's go-ahead, POST `fixtures/expected/postgres-p0/dashboards/postgres-metrics.json` to `/api/import/dashboard?dataset=default`, with `spec.display.name` prefixed `demo-`.
  - Record the status code, the response body shape and **the JSON path of the new ID**.
  - Read the dashboard back with GET, and take a UI screenshot (kept local, outside Git).
- [ ] **Step 3: Import the golden check rule.** POST `fixtures/expected/postgres-monitors/check-rules/<slug>.json` with `name` prefixed `demo-` and `enabled: false`.
  - Record the status code, the response shape, the ID path and the read-back.
  - Confirm that `thresholds{degraded, failed}` and `$__threshold` are accepted.
- [ ] **Step 4: Record answers to the open questions in `docs/STATUS.md`:**
  - Does `TimeSeriesChart` with `spec: {}` render?
  - Is `metadata.project` accepted or ignored?
  - Are `Markdown`, `StatChart` and `ListVariable` rendered? This unblocks plan 05 Tasks 6–7.
  - Are annotation `{{ }}` templates evaluated?
- [ ] **Step 5: Commit** the sanitized fixtures and the status update.

### Task 2: The Dash0 client

**Files:**
- Create: `src/destination/dash0.ts`
- Test: `tests/destination/dash0.test.ts`

**Interfaces:**
- Produces:

```ts
export interface Dash0Config { apiUrl: string; token: string; dataset: string }
export function readDash0Config(env: Record<string, string | undefined>): Dash0Config; // throws InputError("missing env: A, B")
export type PublishOutcome =
  | { status: "imported"; id: string; httpStatus: number }
  | { status: "failed"; httpStatus: number; message: string }
  | { status: "unknown"; message: string };
export function publishDashboard(body: PersesDashboard, cfg: Dash0Config, fetchImpl?: typeof fetch): Promise<PublishOutcome>;
export function publishCheckRule(body: Dash0CheckRule, cfg: Dash0Config, fetchImpl?: typeof fetch): Promise<PublishOutcome>;
export function readBack(kind: "dashboard" | "check-rule", id: string, cfg: Dash0Config, fetchImpl?: typeof fetch): Promise<unknown>;
```

- The ID extraction uses the path recorded in Task 1. Until then, pass the ID path in as a constant, `DASHBOARD_ID_PATH` / `CHECK_RULE_ID_PATH`, and mark it `// UNVERIFIED until plan 07 Task 1`.
- `message` holds the response body cut to 500 characters, with any occurrence of the token replaced by `<redacted>`.

- [ ] **Step 1: Write the failing tests**, using a mock `fetchImpl`.
  - `imports and extracts id`: a 200 response with the recorded shape gives `imported`.
  - `401 is failed`.
  - `abort is unknown`: the mock rejects with an `AbortError`.
  - `sends bearer and dataset`: assert the URL `https://x/api/import/dashboard?dataset=default` and the header `Authorization: Bearer t`.
  - `never leaks the token`: the response body echoes the token, but `message` doesn't contain it.
  - `missing env lists names only`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 3: Receipts

**Files:**
- Create: `src/receipts.ts`
- Test: `tests/receipts.test.ts`

**Interfaces:**
- Produces:

```ts
export interface Receipt { path: string; sha256: string; apiUrl: string; dataset: string; status: "imported" | "failed" | "unknown"; id?: string; httpStatus?: number; message?: string }
export function loadReceipts(dir: string): Receipt[];        // <dir>/import-results.json, [] if absent
export function saveReceipts(dir: string, receipts: Receipt[]): void; // stableStringify, sorted by path
export type ReceiptDecision = "publish" | "skip-unchanged" | "reject-changed" | "reject-unknown";
export function decide(r: Receipt[], path: string, sha256: string, apiUrl: string, dataset: string): ReceiptDecision;
```

- [ ] **Step 1: Write the failing tests.**
  - `unchanged imported is skipped`.
  - `changed artifact is rejected`: the same path, apiUrl and dataset, with an imported status but a different sha, gives `reject-changed`.
  - `timeout yields unknown and blocks re-publish`: an existing `unknown` gives `reject-unknown`.
  - `other destination publishes`: a different dataset gives `publish`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** It must PASS. **Step 5: Commit.**

### Task 4: The publish command

**Files:**
- Create: `src/publish.ts`
- Modify: `src/cli.ts`
- Test: `tests/publish.test.ts`

**Interfaces:**
- Produces:
  - `export interface PublishOptions { from: string; dryRun: boolean; allowPartial: boolean }`
  - `export function runPublish(opts: PublishOptions, env: Record<string, string | undefined>, fetchImpl?: typeof fetch): Promise<{ exitCode: 0 | 1 | 2; receipts: Receipt[]; lines: string[] }>`

**Selection:**

- Manifest entries of kind `dashboard` or `check-rule` are selected when `outcome === "translated"`, or when `outcome === "partial"` and `allowPartial` is set. `blocked` is never selected.
- Prometheus rule files are not published.

**Validation before any write:**

- The manifest parses.
- Each path resolves inside `from`.
- The file's sha256 matches the manifest.
- The body passes `validateDashboard` or `validateCheckRule`.

**Dry run:** print `DRY-RUN POST <apiUrl>/api/import/<kind>?dataset=<ds>  <name>  (<decision>)` per entry, with no fetch calls.

- [ ] **Step 1: Write the failing tests**, using a mock fetch and a temporary run dir built from the plan 04 golden.
  - `dry run makes no requests`.
  - `rejects paths outside the run dir`.
  - `rejects hash mismatch`.
  - `stops on auth failure`: after the first 401 there are no further calls, and the exit code is 1.
  - `partial requires allow-partial`: exit 2 and the partial dashboard is skipped; with the flag, it's published.
  - `writes receipts per asset`: the second asset fails, so the receipts show `imported` and `failed`, and the exit code is 1.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement it.** **Step 4: Verify.** `npm test && npm run typecheck` must pass. **Step 5: Commit.**

### Task 5: Live publish and evidence (needs the token and the user's go-ahead)

- [ ] **Step 1:** Run `npm run dev -- publish --from <golden run dir> --dry-run`, and review the plan with the user.
- [ ] **Step 2:** With the user's go-ahead, run it without `--dry-run`. Record the returned IDs from `import-results.json`.
- [ ] **Step 3:** Read each resource back. In the Dash0 UI, confirm the Connections chart shows `astronomy_db` and `postgres`, and the check rule shows the expression, window and thresholds, and is disabled.
- [ ] **Step 4:** Update `docs/STATUS.md` with the IDs (sanitized), the evidence location and `api: passed`. Set `semantics` only after the plan 09 threshold demo. Mark plan 07 Done in `docs/handoff/README.md`, and commit.
