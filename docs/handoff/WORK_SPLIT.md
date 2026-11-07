# Two-person work split

Two tracks that run in parallel over plans 01–10. This file adds only order, file ownership and
sync points; what each task does stays in its plan. `04.T2` means plan 04, Task 2.

- **Track A — query and dashboard translation:** parser, query compiler, dashboard converter,
  coverage ladder.
- **Track B — CLI, outputs, monitors and Dash0 delivery:** package and shared contracts, writers,
  validation, wiring, goldens, monitors, publish, demo, fetch.

Every task below is a GitHub issue labelled [`track:A`](https://github.com/XNotAGuestX/thinchackdash/issues?q=is%3Aopen+label%3Atrack%3AA) or
[`track:B`](https://github.com/XNotAGuestX/thinchackdash/issues?q=is%3Aopen+label%3Atrack%3AB), with its dependencies set as "blocked by" links. Claim tasks
by assigning their issues.

## Day 0 (together)

- [ ] The integration branch is `main`: one branch and PR per issue, reviewed by XNotAGuestX and merged by Felix or his agent (`AGENTS.md`).
      The starter/fork decision is [#2](https://github.com/XNotAGuestX/thinchackdash/issues/2).
- [ ] Track B lands 01.T1–T2 first (S1).

## Timeline

| Phase | Track A | Track B | Ends with |
|---|---|---|---|
| 1 | Read `00-context.md`; draft 02.T1 tests | 01.T1–T2 | S1 |
| 2 | 02.T1, 03.T3, 02.T2 | 03.T1–T2, 01.T3–T6, 03.T4, 04.T2, 06.T1–T2 | S2–S5 |
| 3 | 04.T1, 06.T3 (code) | 07.T2–T3, 04.T3, 04.T4 + 05.T0 | S6, **S7 = MVP converter** |
| 4 | 06.T3 (entry), 05.T1–T8 | 07.T4, 06.T4–T5, 09.T2, 10.T1, 07.T1, 08.T2–T3 drafts | S8–S10 |
| 5 | 08.T1, 08.T4 | 05.T9, 08.T2–T3 goldens, 07.T5, 09.T3–T4, 10.T2 | — |

## Sync points

| # | What lands | From | Unblocks |
|---|---|---|---|
| S1 | Package, `src/migrator/target.py`, `src/migrator/write.py` (01.T1–T2) | B | All of Track A |
| S2 | `src/migrator/promql.py`, `mapping.py` (03.T1–T2). Both files then belong to Track A | B | 03.T3 |
| S3 | Pinned postgres fixtures, `SourceAsset`, provider table (01.T4–T5) | B | 02.T2, 04.T1 |
| S4 | `parseMetricQuery` (02.T1) | A | 06.T1 |
| S5 | `compileMetricQuery` (03.T3) | A | 06.T4 |
| S6 | `compileDashboard` and synthetic fixtures (04.T1) | A | 04.T2 last case, 04.T3 |
| S7 | P0 golden and frozen mapping (04.T4, 05.T0) | B | Any edit to `mappings/datadog/postgres.json`, any 05 merge, 07.T4, 10.T2 |
| S8 | `expression` kind and the ratio entry (06.T3) | A | 06.T4 |
| S9 | Dash0 contract answers (07.T1; needs blocker B1) | B | "Renders in Dash0" claims for 05.T6–T7 |
| S10 | Coverage ladder done (05.T1–T8) | A | 05.T9, 08 goldens |

## Track A

- [ ] 02.T1. Needs S1. Gives S4.
- [ ] 03.T3. Needs S2. Gives S5.
- [ ] 02.T2. Needs S3.
- [ ] 04.T1. Needs S3. Gives S6.
- [ ] 06.T3 Steps 1–2, tests with an inline mapping.
- [ ] 06.T3 Steps 3–5. Needs S7. Gives S8.
- [ ] 05.T1, then 05.T2–T4. Needs S7. Track B reviews the new mapping entries.
- [ ] 05.T5.
- [ ] 05.T6–T7. S9 is needed only before calling the output "renders in Dash0".
- [ ] 05.T8. Gives S10.
- [ ] 08.T1 (Kafka). Needs S10 and 06.T5.
- [ ] 08.T4 (Docker). Needs S10.

## Track B

- [ ] 01.T1–T2. Gives S1.
- [ ] 03.T1–T2. Gives S2. The `parseMapping` call goes into `__init__.py` with 01.T5.
- [ ] 01.T3–T5. Gives S3.
- [ ] 01.T6.
- [ ] 03.T4. Track A reviews the entry.
- [ ] 04.T2. Until S6, test against a hand-built dashboard.
- [ ] 06.T1, then 06.T2. Needs S4.
- [ ] 07.T2–T3, with mocks.
- [ ] 04.T3. Needs S6.
- [ ] 04.T4, then 05.T0 straight after. Gives S7.
- [ ] 07.T4. Needs S7.
- [ ] 06.T4. Needs S5 and S8.
- [ ] 06.T5. The monitor golden reads a frozen mapping copy under `fixtures/mappings/`.
- [ ] 09.T2 and 10.T1 (mocked): any time, between waits.
- [ ] 07.T1. Needs blocker B1 and the user's go-ahead. Gives S9.
- [ ] 08.T2 (Redis), 08.T3 (nginx). Pinning and mapping drafts any time after S2; goldens need
      S10. Track A reviews the entries.
- [ ] 05.T9. Needs S10.
- [ ] 07.T5. Needs 07.T1 and the user's go-ahead.
- [ ] 09.T3–T4, after 07.T5.
- [ ] 10.T2. Needs S7; its live step needs blocker B3.
- [ ] 09.T5 only on the user's request. 09.T1 belongs to whoever owns blocker B2.

## File ownership

| Track A | Track B |
|---|---|
| `src/migrator/source/datadog/{model,parse_query,compile_query,dashboard,formula}.py` | Everything else under `src/`, including `monitor.py`, `__init__.py`, `validation.py`, `destination/` |
| `src/migrator/promql.py`, `src/migrator/source/datadog/mapping.py` (after S2) | `pyproject.toml`, `uv.lock`, `.python-version` |
| `mappings/datadog/postgres.json` (after S7), `kafka.json`, `docker.json` | `mappings/datadog/redis.json`, `nginx.json`; `fixtures/mappings/` |
| `fixtures/datadog/synthetic/` | `fixtures/datadog/integrations-core/`, `fixtures/expected/`, `fixtures/dash0/`, `scripts/` |
| | `tests/test_golden.py`, `README.md`, `docs/DEMO.md` |

Tests belong to the owner of the file they cover. Track B appends the monitor types to `model.py`
in 06.T1. Track A adds its Kafka and Docker golden cases as separate `describe` blocks and pins its
own service folders. New dependencies go through Track B.

## Rules for working in parallel

1. Don't edit the other track's files without asking first, in the issue concerned.
2. From S7 on, a change that alters an expected tree regenerates it in the same commit, and the
   other track reviews the diff. The P0 tree changes with 05.T1, 05.T5, 05.T7 and 05.T8, because
   05.T0 freezes the mapping, not the compiler.
3. A golden that reads a mapping file reads a frozen copy, because `report.json` records the
   mapping hash. 05.T9 is the exception: it runs after the last `postgres.json` edit.
4. Mapping entries are reviewed by the other track's person, who sets `reviewed` personally.
   Request it with the `needs:review` label and a comment in the issue.
5. Announce each sync point in its issue when the PR is merged; the waiting track watches it.
6. When a track's list is done, it claims unstarted issues from the other track's tail (08, 10)
   by reassigning them and relabelling the track.
