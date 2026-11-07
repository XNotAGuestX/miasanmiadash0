# 09 — Demo telemetry, runbook and submission: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live demo reliable, and submit the work. This is **not converter work**. It covers keeping the telemetry durable, causing a controlled threshold crossing for the check rule, an accurate runbook and README, and the fork plus PR the challenge requires.

**Architecture:** One small shell script for the threshold crossing, plus documentation. No product code.

**Tech Stack:** POSIX shell, Docker CLI, psql inside the Postgres container.

**Spec:** [00-context.md](00-context.md) §1; [DASH0_INVENTORY.md](../DASH0_INVENTORY.md#caveats) (caveats 1 and 4); `AGENTS.md` ("Credentials and live operations", "Verification and completion"); `docs/SOURCES.md` (submission workflow).

**Depends on:** plan 07 for the live parts.

**Blocked by:** open blocker **B2**, the demo telemetry owner. The fork and PR also need the user's explicit request.

## Global Constraints

- Change only demo resources: a `demo-` prefix and the `default` dataset. Enable only the demo check, and only during a requested live verification.
- The script never prints passwords. It reads `PGUSER`, `PGDATABASE` and `PGPASSWORD` from the environment, and the container name from `PG_CONTAINER`.
- Never present generated JSON as a migrated dashboard. Evidence is returned IDs, read-back output and UI screenshots.

## Review Focus

1. **Ctrl-C or a crashed script:** every held connection is released (`trap` kills the children). Covered by `cleanup releases connections` (Task 2).
2. **A count that would exceed `max_connections`:** refuse before opening anything, so the demo database isn't locked out. Covered by `refuses to exceed max_connections` (Task 2).
3. **Telemetry stopped during the demo:** the runbook has a fallback with clearly labelled earlier evidence. Covered in Task 3.
4. **The check window needs 15 minutes of data:** the runbook schedules the crossing ahead of time. Covered in Task 3.
5. **Secrets in PR artifacts:** a grep gate runs before the push. Covered in Task 5.

---

### Task 1: Durable telemetry (owner: B2)

- [ ] **Step 1:** The owner records in `docs/DEMO.md` exactly how the local OTel Demo with the Dash0 exporter is started: the repository, version, compose command and the env var names (no values).
- [ ] **Step 2:** Decide whether to keep that machine running for the demo or move it to an always-on host. Record the decision and the owner in `docs/STATUS.md`.
- [ ] **Step 3:** Verify, read-only, that `max by (postgresql_database_name) (postgresql.backends)` returns data for the last 30 minutes before each rehearsal.

### Task 2: Connection-holder script

**Files:**
- Create: `scripts/hold-pg-connections.sh`
- Test: `tests/scripts/test_hold_pg_connections.py` (runs the script with `--dry-run`)

**Interface:** `scripts/hold-pg-connections.sh <count> <seconds> [--dry-run]`.

1. Read `max_connections` and the current connection count with `docker exec $PG_CONTAINER psql -tAc ...`.
2. If current + count ≥ `max_connections`, exit 1 with `refusing: would exceed max_connections`.
3. Otherwise start `<count>` background `docker exec $PG_CONTAINER psql -c "select pg_sleep(<seconds>)"` sessions.
4. `trap` EXIT, INT and TERM to kill them; wait for them.

With `--dry-run`, print the commands instead of running them.

- [ ] **Step 1: Write the failing tests.**
  - `dry run prints count sessions`: with a stub `docker` on `PATH` returning `100` and `8`, `70 900 --dry-run` prints 70 `pg_sleep(900)` lines.
  - `refuses to exceed max_connections`: `95 60` exits 1.
  - `cleanup releases connections`: under the stub, sending SIGINT leaves no stub child processes.
- [ ] **Step 2: Implement the script.** Run `uv run migrator test tests/scripts`; it must PASS. Run `shellcheck scripts/hold-pg-connections.sh` if it's available. Commit.
- [ ] **Step 3: Work out the crossing numbers.** Usage is (current + N) / max. At current ≈ 8 and max = 100:
  - `N = 75` gives about 0.83, past the 0.8 warning (degraded);
  - `N = 85` gives about 0.93, past the 0.9 critical (failed).
  - `backends` counts background workers too, so measure the current value just before starting.
  - Hold each step longer than 15 minutes, because of the `avg_over_time` window. Record the actual values used.

### Task 3: Rewrite the demo runbook

**Files:**
- Modify: `docs/DEMO.md`

- [ ] Replace the generic `demo.temperature` flow with the Postgres flow:
  1. the source dashboard and monitor (integrations-core files);
  2. `convert`, with the golden outputs and the report;
  3. the unsupported example: `replication_delay` is blocked, along with the widgets blocked in "Postgres - Metrics";
  4. `publish --dry-run`, then `publish`;
  5. the Dash0 UI: the chart with `astronomy_db` and `postgres`;
  6. the check rule enabled for the demo, with degraded and then failed shown from captured evidence (the crossing needs ≥ 15 minutes);
  7. the limits.
- [ ] Add the fallback: earlier evidence, clearly labelled as earlier. Commit.

### Task 4: README and limits

- [ ] Rewrite `README.md` as the final usage document:
  - install, test, `convert` and `publish`, using only commands that have actually been run;
  - the supported widget, query and monitor subset;
  - the env vars;
  - the known limits (from the report codes and `docs/DASH0_INVENTORY.md#caveats`).
- [ ] Remove the "project handoff only" statement once plan 04 is done. Commit.

### Task 5: Fork, branch and PR (only on the user's explicit request)

- [ ] **Step 1:** Fork `vimouzin/dash0-dashboard-migrator`. Add it as a remote, and push a feature branch containing this repository's history; don't force anything onto unrelated history without a team decision.
- [ ] **Step 2: Secret gate.** `git grep -nE "auth_[A-Za-z0-9]{8,}|DD_API_KEY=.+|DASH0_AUTH_TOKEN=.+"` must print nothing, and `artifacts/` and `private-input/` must be untracked.
- [ ] **Step 3:** Open the PR against upstream `main`, with an implementation summary, features, setup and usage, validation evidence (offline, mocked and live, kept separate) and the known limits.
