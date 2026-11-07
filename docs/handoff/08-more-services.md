# 08 — More services (Kafka, Redis, nginx, Docker): implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend conversion to the next services, in the data-driven order (decision D5): Kafka → Redis → nginx → Docker. Mostly this means **adding mapping files and fixtures**, not compiler code. Each service ends with a reviewed golden.

**Architecture:**

- There's one mapping file per service, at `mappings/datadog/<service>.json`.
- Pin the integrations-core assets at the same SHA, under `fixtures/datadog/integrations-core/<service>/`.
- A compiler change is only allowed when a service needs a construct that no plan supports yet. Add it as a new task here with its own test, never as a quiet special case.

**Tech Stack:** As before.

**Spec:** [00-context.md](00-context.md) §3 (A1) and §6; [DASH0_INVENTORY.md](../DASH0_INVENTORY.md) (the label and metric lists per service).

**Depends on:** plans 04 and 05; Kafka monitors also depend on plan 06.

## Global Constraints

- **Before** writing any mapping entry, check its target metric name, type and labels in Dash0 with a read-only catalog or PromQL query. Record the query in the entry's `ref`.
- Cite a row of Datadog's metrics_mapping table where one exists. Otherwise give the reasoning, and leave the entry for a human reviewer.
- `reviewed: null` until a human reviews the entry.
- Pin fixtures at `a9b9e42b7e484861ecbd1f5919da7c52a694b74d`. Use only each service's `assets/dashboards` and `assets/monitors` files.

## Review Focus

1. **Metrics present in Datadog but absent in Dash0** (`redis.mem.maxmemory`, Kafka zookeeper, nginx Plus): report `MISSING_METRIC_MAPPING` for them. There must be no mapping entry for them at all. Covered by each service's golden test.
2. **Label names that churn per restart** (Kafka `service_instance_id` is a random UUID): a grouped alert must not silently fan out into stale groups. Record this in the mapping review, and use `grain` where the source series grain differs. Covered by `kafka produce latency groups by broker` (Task 1).
3. **Units:** Datadog reports some byte counters as rates (`kafka.net.bytes_in.rate`) and some percentages on a 0–100 scale. Each `rate` or `scale` choice cites a doc. Covered by the review step in each task.
4. **Anomaly-based monitors** (all nginx monitors and Kafka's producer-rate monitor) stay blocked. Covered by each golden.
5. **A screenboard whose top level is all `group` widgets:** handled through plan 05 Task 7. Covered by the Redis and Kafka goldens' widget counts.

---

### Task 1: Kafka

The best second-monitor candidate.

**Files:**
- Create: `fixtures/datadog/integrations-core/kafka/{dashboards/kafka_dashboard.json,monitors/kafka_offline_partition.json,monitors/broker_produce_latency.json,monitors/kafka_high_producer_request_rate.json}`
- Create: `mappings/datadog/kafka.json`, `fixtures/expected/kafka/`
- Test: `tests/golden.test.ts` (new case `kafka golden`)

**Mapping entries.** Verify each in Dash0 first.

| Datadog | kind | Dash0 target | Labels / matchers | Status |
|---|---|---|---|---|
| `kafka.replication.offline_partitions_count` | gauge | `kafka.partition.offline` (sum) | `instance` → `service_instance_id` | present (JMX) |
| `kafka.replication.under_replicated_partitions` | gauge | `kafka.partition.underReplicated` (sum) | same | present |
| `kafka.request.produce.time.99percentile` | gauge | `kafka.request.time.99p` (gauge, ms) | matcher `type="Produce"`; `instance` → `service_instance_id` | present |
| `kafka.request.fetch_consumer.time.avg`, `kafka.request.produce.time.avg` | — | none (only 50p/99p exist) | — | leave unmapped |
| `kafka.replication.unclean_leader_elections.rate` | rate | `kafka.leaderElection.unclean.count` (sum) | — | present |
| `kafka.replication.isr_shrinks.rate`, `isr_expands.rate` | rate | `kafka.isr.operation.count` (sum) | matcher on the operation label: **check the label name and values first** | verify |
| `kafka.net.bytes_in.rate`, `bytes_out.rate` | rate | `kafka.network.io` (sum, By) | direction label: **check first** | verify |
| `kafka.request.{producer,fetch}_request_purgatory.size` | gauge | `kafka.purgatory.size` (sum) | type label: **check first** | verify |
| `kafka.consumer_lag` | gauge | `kafka.consumer_group.lag` (gauge) | `consumer_group` → `group`, `topic` → `topic` | present (kafkametrics) |

- [ ] **Step 1: Pin the fixtures.** Use the plan 01 Task 4 command with `kafka/assets/...` paths. Append the files to `NOTICE.md`.
- [ ] **Step 2: Write the failing test `kafka golden`.**
  - `kafka_offline_partition` is **translated**, with check-rule thresholds `{degraded: 0, failed: 1}` and the expression `avg_over_time((avg ({otel_metric_name="kafka.partition.offline", otel_metric_type="sum"}))[5m:1m]) > $__threshold`.
  - `kafka produce latency groups by broker`: `broker_produce_latency` is translated, its expression contains `avg by (service_instance_id) (` and `type="Produce"`, and its thresholds are `{degraded: 100, failed: 200}`.
  - `kafka_high_producer_request_rate` is blocked with `UNSUPPORTED_QUERY_FUNCTION` (`anomalies`).
  - The dashboard is `partial`. Record the exact counts after the first reviewed run.
  - The options of the 2 translated monitors must pass the plan 06 allowlist. If one doesn't, the test asserts the blocking code instead. **Don't** widen the allowlist without a human decision.
- [ ] **Step 3: Write `mappings/datadog/kafka.json`.** Then generate the expected tree, review it by hand and commit it.
- [ ] **Step 4: Check against real data (read-only).** Run both monitor conditions in Dash0. Expect offline = 0 and Produce p99 of about 14 ms on 2026-11-07. Request a human review, then commit.

### Task 2: Redis

**Files:**
- Create: `fixtures/datadog/integrations-core/redisdb/{dashboards/overview.json,monitors/high_mem.json}`
- Create: `mappings/datadog/redis.json`, `fixtures/expected/redis/`

**Mapping entries.** Verify the type and labels of each in Dash0 first.

| Datadog | kind | Dash0 target |
|---|---|---|
| `redis.mem.used`, `redis.mem.rss`, `redis.mem.fragmentation_ratio` | gauge | `redis.memory.used`, `redis.memory.rss`, `redis.memory.fragmentation_ratio` |
| `redis.net.clients`, `redis.clients.blocked` | gauge | `redis.clients.connected`, `redis.clients.blocked` (sum) |
| `redis.stats.keyspace_hits`, `redis.stats.keyspace_misses` | rate | `redis.keyspace.hits`, `redis.keyspace.misses` |
| `redis.net.commands` | rate | `redis.commands.processed` |
| `redis.net.rejected` | rate | `redis.connections.rejected` |
| `redis.keys.evicted`, `redis.keys.expired` | rate | `redis.keys.evicted`, `redis.keys.expired` (check that Datadog reports them as rates) |
| `redis.keys`, `redis.expires` | gauge | `redis.db.keys`, `redis.db.expires` |
| `redis.rdb.changes_since_last` | gauge | `redis.rdb.changes_since_last_save` |
| `redis.net.slaves` | gauge | `redis.slaves.connected` |
| `redis.cpu.sys`, `redis.cpu.user` | rate | `redis.cpu.time`, with a state matcher: **check the label first** |

**Leave unmapped:** `redis.mem.maxmemory` (absent in Dash0), `redis.info.latency_ms`, `redis.slowlog.*`, `redis.key.length` and `redis.replication.*`.

- [ ] **Step 1: Pin the fixtures.**
- [ ] **Step 2: Write the failing test `redis golden`.**
  - `high_mem` is blocked with `UNSUPPORTED_QUERY_SYNTAX` (the `100 * a / b` arithmetic, plan 06 Task 1).
  - The dashboard is `partial`, with the counts recorded after review.
- [ ] **Step 3: Write the mapping file.** Generate and review the expected tree, run the live read-only check, request a human review, and commit.

### Task 3: nginx

**Files:**
- Create: `fixtures/datadog/integrations-core/nginx/{dashboards/NGINX-Metrics_dashboard.json,monitors/*.json}` (7 monitors)
- Create: `mappings/datadog/nginx.json`, `fixtures/expected/nginx/`

**Mapping entries:**

- `nginx.net.connections` → `nginx.connections_current` with `state="active"`.
- `nginx.net.reading`, `nginx.net.writing`, `nginx.net.waiting` → `nginx.connections_current` with `state` set to `reading`, `writing` or `waiting`. Check the state values first.
- `nginx.net.request_per_s` → `rate(nginx.requests)`.
- `nginx.net.conn_dropped_per_s` → an `expression`: `rate(accepted[$__rate_interval]) - rate(handled[$__rate_interval])`, with `$filters`. It needs a human review.

**Leave unmapped:** `nginx.server_zone.*` (Plus).

- [ ] **Step 1: Pin the fixtures.** **Step 2: Write `nginx golden`.** All 7 monitors are blocked: `UNSUPPORTED_QUERY_FUNCTION` for `anomalies`, or `MISSING_METRIC_MAPPING` for Plus-only metrics. The dashboard is `partial`.
- [ ] **Step 3: Write the mapping file.** Generate and review the expected tree, request a human review, and commit.

### Task 4: Docker (lowest priority)

- [ ] **Step 1: Pin `docker_daemon/assets/dashboards/docker_dashboard.json`.** Inventory the `container.*` metrics, types, units and labels in Dash0 (the full catalog, page by page).
- [ ] **Step 2: Map only the pairs that can be justified.** For example, Datadog `docker.cpu.user` (percent) versus OTel `container.cpu.usage.usermode` (ns, cumulative) needs `rate` plus a scale of `100 / 1e9`. That gets a human review, or else stays unmapped.
- [ ] **Step 3: Write the golden.** Run the review, then commit.
