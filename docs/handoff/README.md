# Open work

**Target:** a deterministic CLI that converts Datadog dashboards (and metric monitors) into Perses dashboards (and Prometheus/Dash0 check rules), with a per-item report. **No LLM takes part in any conversion step** (`AGENTS.md`).

Plans 01–07 and 10 are implemented and merged; their plan files were removed (git history and the `main-pre-rip` branch keep them). The code and its tests are the source of truth. [00-context.md](00-context.md) is the shared spec (decisions, diagnostic codes, outcome model). Only plans with open tasks remain: [08](08-more-services.md), [09](09-demo-and-submission.md) and [11](11-engine-alignment.md) (engine alignment).

## Next, in order

| # | Work | Where | Done when | Blocked by |
|---|---|---|---|---|
| 1 | **Mapping review** against Datadog's OTel table and per-metric evidence (Datadog type and source on both sides). Redis/nginx notes in `mappings/datadog/REVIEW-redis-nginx.md`. | [plan 11](11-engine-alignment.md) steps 1–2; #27, #52–#55 | vendor-table and type tests pass; entries set `reviewed` | a human |
| 2 | **Default aggregator** (05.T1): a query without `agg:` uses `avg`. Implemented on branch `default-avg-aggregator`, not merged. | #33 | PR merged, goldens regenerated | — |
| 3 | **Panel heights** are copied unscaled, so panels render squashed in Dash0 (`_GridBuilder.place`). | #89 | reviewed height scale, golden regenerated | approval |
| 4 | **Sparse metrics**: `rate(...[$__rate_interval])` is empty for `system.network.io`. Reviewed per-entry rate window in the mapping. | #90 | entry-level window, test | — |
| 5 | **Converter vs `expected.yaml` disagreements** (6 causes). Settle each by a converter fix or an `overrides.yaml` correction. | #96 | `uv run pytest --include-unreviewed` failures explained or fixed | — |
| 6 | **Service goldens**, Kafka → Redis → nginx → Docker, after their mapping review. | [plan 08](08-more-services.md), #52–#55 | one reviewed golden per service | 1 |
| 7 | **Datadog functions** by frequency (`.weighted()` 36, `top()` 10, `.as_count()` 9, …), each with the documented PromQL equivalent and exact tests, or blocked with a reason. | [plan 11](11-engine-alignment.md) step 3; new issues | each function translated or documented as blocked | — |
| 8 | **Smoke check**: every translated panel returns plausible data in Dash0 (`scripts/smoke_check.py`, read-only). | [plan 11](11-engine-alignment.md) step 4 | Postgres run clean or each flag has an issue | data window (B2) |
| 9 | **Agent0 review** (advisory, last): Agent0 says per panel whether the conversion matches; flags are kept separate and never change output. | [plan 11](11-engine-alignment.md) step 5 | every `different` has a human decision | 8 |
| 10 | **Demo**: durable telemetry, enabled check and threshold crossing (`scripts/hold-pg-connections.sh`), fork and PR. | [plan 09](09-demo-and-submission.md) T1, T5; #56, #60, #2 | rehearsed demo; PR only on the user's request | B2; user |
| 11 | **Live fetch round trip** (code merged, offline-tested). | #62 | fetched folder converts byte-identically | B3 |

Testing loop: [USAGE.md](../../USAGE.md). Agent0 may propose `expected.yaml` cases at development time; they count only after a human sets `reviewed: true`.

## Open decisions and blockers

- **A1** target vocabulary = names and labels as found in Dash0; **A2** alert output = Prometheus rule group + Dash0 check rule; **A3** monitor strictness = approximate and warn on a reviewed allowlist, block the rest. All *assumed defaults* (#1).
- **B1** Dash0 token: resolved. **B2** demo telemetry owner (#4). **B3** Datadog account (#5). Starter/fork relationship (#2).

## Housekeeping

Open issues whose work is merged or moot: #16–#21, #23–#25, #29–#32, #57–#59 and epics #6, #7, #9, #11, #12. Close them once confirmed, e.g. `gh issue close 16 -c "Done on main"`.
