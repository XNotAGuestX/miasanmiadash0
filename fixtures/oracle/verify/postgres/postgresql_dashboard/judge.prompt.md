Read-only task, do not create or change anything. Answer with one YAML code block only.

You are reviewing expected test outcomes for migrating a Datadog dashboard to a Perses dashboard backed by OpenTelemetry metrics, checked against this Dash0 organization (dataset `default`). For each Datadog request below there is a candidate outcome: either PromQL (`translated`) or `blocked` with error codes. The candidates are an unreviewed draft. Some may be wrong. Do not assume a candidate is correct, and do not let it shape your own answer.

Which metric to use:
- First choice: a metric that exists in this dataset (verify with the metric catalog and PromQL).
- If no metric in this dataset measures the same thing, use a metric that OpenTelemetry defines, from the OTel metric list at the end of this prompt (collector-contrib receivers and scrapers, semantic conventions, OTel Java JMX scraper). Such a request is still `translated`; it just cannot be live-checked.
- Block with "no OTel metric" only if neither this dataset nor the OTel metric list has a metric that measures the same quantity.
- Equivalence must come from the metric definitions (what is measured, unit, instrument type), never from similar names alone. Use the attribute keys given for a listed metric (dots become `_` in labels).

Dash0 PromQL conventions:
- Select a metric as `{otel_metric_name="<dotted.name>", otel_metric_type="<sum|gauge|histogram>"}`, with further matchers appended as `, <label>="<value>"`.
- Attribute keys become labels with dots replaced by `_`.
- Use `rate(<selector>[$__rate_interval])` for monotonic sums.
- Template variables with a tag prefix and default `*` (e.g. `$host` on tag `host`) become a matcher `<dash0 label>=~"$<name>"`. Template variables without a prefix (e.g. `$scope`) and default `*` are dropped (all series).

Hard rules. The converter is deterministic; anything these rules do not allow is blocked:
- Any Datadog function blocks the whole request, with reason "unsupported function: <name>". That includes trailing functions (`.rollup()`, `.as_count()`, `.as_rate()`, `.weighted()`, `.fill()`) and wrapping functions (`top()`, `per_second()`, `per_minute()`, `diff()`, `timeshift()`, `week_before()`, `abs()`, `default_zero()`, `count_nonzero()`, `anomalies()`, …), in queries or in formulas. Do not approximate a function with `increase`, `topk`, `*_over_time` or `offset`, and do not drop it. Put the closest PromQL you would have used in `notes` only.
- No numeric constants that are not in the Datadog source. If the units differ (percent vs ratio, ns vs s), say so in `notes` and propose a scale with a documentation link; do not apply it in `promql`.
- Use only `$__rate_interval` as a range. Never `$__interval`, `$__range`, subqueries or fixed windows such as `[15m]`.
- Use `rate()` only on monotonic sums, never on gauges.
- If the Datadog metric has no direct OTel equivalent and would have to be computed from other metrics (e.g. dropped = accepted − handled), block the request and put the proposed expression in `notes`.
- If the Datadog series grain differs from the OTel one (per-CPU vs per-host, series duplicated by restarts), say so in `notes`, naming the label that would collapse it.

Rules: a request is all-or-nothing; if any formula cannot be expressed exactly, the whole request is blocked. Never drop a series. Never invent a metric. A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs) and is blocked.

Error codes of blocked candidates:
- UNSUPPORTED_DATA_SOURCE: no metrics query (logs, events, other data sources).
- UNSUPPORTED_FORMULA: a function in a formula.
- UNSUPPORTED_QUERY_FUNCTION: a Datadog function in a query.
- MISSING_METRIC_MAPPING: no OTel metric measures the same quantity, or it would have to be derived from other metrics.

How to review each request, in this order:
1. Read only the `datadog` side. Write your own result in `independent`: the list of PromQL strings you would expect (one per displayed formula, in formula order), or `blocked: <reason>` under the hard rules above. Decide this before you look at the candidate, and do not change it afterwards.
2. Compare the candidate with your independent result and with the Datadog side: the measured quantity (same metric definition), unit, aggregation (avg/sum/min/max, rate vs raw value), grouping (`by` labels vs Datadog `by {…}` tags and template variables), and the outcome (translated vs blocked, and the block reason).
3. Run every candidate PromQL against dataset `default` over 2026-11-07 14:00–15:25 UTC (receiver data only exists in that window) and report the number of series it returns in `live_check`. Where it helps, run your independent PromQL too and compare the series counts. For a metric that is not in the dataset (see the OTel metric list at the end), write `not in dataset`; for a blocked candidate, write `n/a (blocked)`.
4. Set each check to `ok`, `differs` or `n/a`, then the verdict.

Verdicts:
- pass: the candidate has the same quantity, unit, aggregation, grouping and series as the Datadog request; or the candidate is blocked for a correct reason.
- nit: the candidate gives the same numbers apart from a documented unit scale, a grain caveat, or a cosmetic difference (label order, matcher style, redundant parentheses).
- block: a different quantity, aggregation, grouping or series count; or a wrong outcome (translated although the rules require blocking, or blocked although an exact translation exists, or blocked with the wrong code).

For every request below, answer with one YAML list item, in the given order:
- source_path: <as given>
  independent: [<your PromQL strings>]   # or a string "blocked: <reason>"
  verdict: pass | nit | block
  checks: {quantity: ok|differs|n/a, unit: ok|differs|n/a, aggregation: ok|differs|n/a, grouping: ok|differs|n/a, series_count: ok|differs|n/a, outcome: ok|differs}
  live_check: <series count of the candidate PromQL in the window, e.g. "3 series"; "not in dataset"; "n/a (blocked)">
  reasons: [<one short reason per differing check>]   # required for nit and block; [] for pass
  notes: <optional caveats, e.g. the closest PromQL for a blocked request>

Answer for every request exactly once. Quote every YAML string value that contains a colon.

Dashboard: `Postgres - Metrics` (`postgres/assets/dashboards/postgresql_dashboard.json`), template variables: $scope (default `*`).

Requests (15):
- source_path: widgets[0].definition.requests[0]
  datadog: {widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_fetched{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['avg(rate({otel_metric_name="postgresql.tup_fetched", otel_metric_type="sum"}[$__rate_interval]))']}
- source_path: widgets[0].definition.requests[1]
  datadog: {widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_returned{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['avg(rate({otel_metric_name="postgresql.tup_returned", otel_metric_type="sum"}[$__rate_interval]))']}
- source_path: widgets[0].definition.requests[2]
  datadog: {widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_inserted{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['avg(rate({otel_metric_name="postgresql.tup_inserted", otel_metric_type="sum"}[$__rate_interval]))']}
- source_path: widgets[0].definition.requests[3]
  datadog: {widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_updated{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['avg(rate({otel_metric_name="postgresql.tup_updated", otel_metric_type="sum"}[$__rate_interval]))']}
- source_path: widgets[1].definition.requests[0]
  datadog: {widget: 'timeseries: Connections', queries: {query1: 'avg:postgresql.connections{$scope} by {db}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['avg by (postgresql_database_name) ({otel_metric_name="postgresql.backends", otel_metric_type="sum"})']}
- source_path: widgets[2].definition.requests[0]
  datadog: {widget: 'timeseries: Inserts / updates / deletes (per sec)', queries: {query1: 'postgresql.rows_inserted{$scope}', query2: 'postgresql.rows_deleted{$scope}', query3: 'postgresql.rows_updated{$scope}'}, formulas: [query1, query2, query3]}
  candidate: {outcome: blocked, errors: [MISSING_AGGREGATOR]}
- source_path: widgets[3].definition.requests[0]
  datadog: {widget: 'timeseries: Disk utilization (%)', queries: {query1: 'avg:system.io.util{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['100 * avg(rate({otel_metric_name="system.disk.io_time", otel_metric_type="sum"}[$__rate_interval]))']}
- source_path: widgets[4].definition.requests[0]
  datadog: {widget: 'timeseries: System load', queries: {query1: 'system.load.1{$scope}'}, formulas: [query1]}
  candidate: {outcome: blocked, errors: [MISSING_AGGREGATOR]}
- source_path: widgets[4].definition.requests[1]
  datadog: {widget: 'timeseries: System load', queries: {query1: 'system.load.5{$scope}'}, formulas: [query1]}
  candidate: {outcome: blocked, errors: [MISSING_AGGREGATOR]}
- source_path: widgets[4].definition.requests[2]
  datadog: {widget: 'timeseries: System load', queries: {query1: 'system.load.15{$scope}'}, formulas: [query1]}
  candidate: {outcome: blocked, errors: [MISSING_AGGREGATOR]}
- source_path: widgets[5].definition.requests[0]
  datadog: {widget: 'timeseries: CPU usage (%)', queries: {query1: 'system.cpu.idle{$scope}', query2: 'system.cpu.system{$scope}', query3: 'system.cpu.iowait{$scope}', query4: 'system.cpu.user{$scope}', query5: 'system.cpu.stolen{$scope}', query6: 'system.cpu.guest{$scope}'}, formulas: [query1, query2, query3, query4, query5, query6]}
  candidate: {outcome: blocked, errors: [MISSING_AGGREGATOR]}
- source_path: widgets[6].definition.requests[0]
  datadog: {widget: 'timeseries: I/O wait (%)', queries: {query1: 'max:system.cpu.iowait{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['100 * max(avg by (host_name) (rate({otel_metric_name="system.cpu.time", otel_metric_type="sum", cpu_mode="wait"}[$__rate_interval])))']}
- source_path: widgets[7].definition.requests[0]
  datadog: {widget: 'timeseries: System memory', queries: {query1: 'sum:system.mem.usable{$scope}', query2: 'sum:system.mem.total{$scope}'}, formulas: [query1, query2 - query1]}
  candidate: {outcome: blocked, errors: [MISSING_METRIC_MAPPING]}
- source_path: widgets[8].definition.requests[0]
  datadog: {widget: 'timeseries: Network traffic (per sec)', queries: {query1: 'sum:system.net.bytes_rcvd{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['sum(rate({otel_metric_name="system.network.io", otel_metric_type="sum", system_network_direction="receive"}[$__rate_interval]))']}
- source_path: widgets[8].definition.requests[1]
  datadog: {widget: 'timeseries: Network traffic (per sec)', queries: {query1: 'sum:system.net.bytes_sent{$scope}'}, formulas: [query1]}
  candidate: {outcome: translated, promql: ['sum(rate({otel_metric_name="system.network.io", otel_metric_type="sum", system_network_direction="transmit"}[$__rate_interval]))']}

OTel metric list (pinned definitions; "in dataset" from a snapshot of dataset `default`):
- postgresql.backends (non-monotonic sum, unit 1; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.bgwriter.buffers.allocated (monotonic sum, unit {buffers}; attributes: none; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.bgwriter.buffers.writes (monotonic sum, unit {buffers}; attributes: bg_buffer_source; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.bgwriter.checkpoint.count (monotonic sum, unit {checkpoints}; attributes: bg_checkpoint_type; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.bgwriter.duration (monotonic sum, unit ms; attributes: bg_duration_type; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.bgwriter.maxwritten (monotonic sum, unit 1; attributes: none; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.blks_hit (monotonic sum, unit {blks_hit}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.blks_read (monotonic sum, unit {blks_read}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.blocks_read (monotonic sum, unit 1; attributes: db.collection.name, db.namespace, source; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.commits (monotonic sum, unit 1; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.connection.max (gauge, unit {connections}; attributes: none; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.database.count (non-monotonic sum, unit {databases}; attributes: none; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.database.locks (gauge, unit {lock}; attributes: db.namespace, lock_type, mode, relation; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.db_size (non-monotonic sum, unit By; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.deadlocks (monotonic sum, unit {deadlock}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.function.calls (monotonic sum, unit {call}; attributes: db.namespace, function; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.index.scans (monotonic sum, unit {scans}; attributes: db.collection.name, db.namespace, postgresql.index.name; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.index.size (gauge, unit By; attributes: db.collection.name, db.namespace, postgresql.index.name; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.operations (monotonic sum, unit 1; attributes: db.collection.name, db.namespace, operation; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.query.conflicts (monotonic sum, unit {query}; attributes: db.namespace, postgresql.conflict.type; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.query.execution.time (monotonic sum, unit s; attributes: db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.replication.data_delay (gauge, unit By; attributes: replication_client; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.rollbacks (monotonic sum, unit 1; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.rows (non-monotonic sum, unit 1; attributes: db.collection.name, db.namespace, state; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.sequential_scans (monotonic sum, unit {sequential_scan}; attributes: db.collection.name, db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.table.count (non-monotonic sum, unit {table}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.table.size (non-monotonic sum, unit By; attributes: db.collection.name, db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.table.vacuum.count (monotonic sum, unit {vacuum}; attributes: db.collection.name, db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.temp.io (monotonic sum, unit By; attributes: db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.temp_files (monotonic sum, unit {temp_file}; attributes: db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.tup_deleted (monotonic sum, unit {tup_deleted}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.tup_fetched (monotonic sum, unit {tup_fetched}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.tup_inserted (monotonic sum, unit {tup_inserted}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.tup_returned (monotonic sum, unit {tup_returned}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.tup_updated (monotonic sum, unit {tup_updated}; attributes: db.namespace; in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.vector.insert.duration (monotonic sum, unit s; attributes: db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.vector.insert.rows (monotonic sum, unit {vectors}; attributes: db.namespace; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.vector.search.calls (monotonic sum, unit {search}; attributes: db.namespace, postgresql.distance.function.name; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.vector.search.duration (monotonic sum, unit s; attributes: db.namespace, postgresql.distance.function.name; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.vector.search.rows_returned (monotonic sum, unit {rows}; attributes: db.namespace, postgresql.distance.function.name; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.wal.age (gauge, unit s; attributes: none; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.wal.delay (gauge, unit s; attributes: replication_client, wal_operation_lag; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- postgresql.wal.lag (gauge, unit s; attributes: replication_client, wal_operation_lag; not in dataset; collector-contrib/receiver/postgresqlreceiver/metadata.yaml)
- system.cpu.frequency (gauge, unit Hz; attributes: cpu.frequency, cpu.logical_number; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/metadata.yaml)
- system.cpu.load_average.15m (gauge, unit {thread}; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/loadscraper/metadata.yaml)
- system.cpu.load_average.1m (gauge, unit {thread}; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/loadscraper/metadata.yaml)
- system.cpu.load_average.5m (gauge, unit {thread}; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/loadscraper/metadata.yaml)
- system.cpu.logical.count (non-monotonic sum, unit {cpu}; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/metadata.yaml)
- system.cpu.physical.count (non-monotonic sum, unit {cpu}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/metadata.yaml)
- system.cpu.time (monotonic sum, unit s; attributes: cpu, cpu.logical_number, cpu.mode, state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/metadata.yaml)
- system.cpu.utilization (gauge, unit 1; attributes: cpu, cpu.logical_number, cpu.mode, state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/metadata.yaml)
- system.disk.io (monotonic sum, unit By; attributes: device, direction, disk.io.direction, system.device.name; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.io_time (monotonic sum, unit s; attributes: device, system.device.name; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.limit (non-monotonic sum, unit By; attributes: system.device.name; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.disk.merged (monotonic sum, unit {operations}; attributes: device, direction, disk.io.direction, system.device.name; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.operation_time (monotonic sum, unit s; attributes: device, direction, disk.io.direction, system.device.name; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.operations (monotonic sum, unit {operations}; attributes: device, direction, disk.io.direction, system.device.name; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.pending_operations (non-monotonic sum, unit {operations}; attributes: device; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.disk.weighted_io_time (monotonic sum, unit s; attributes: device; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/diskscraper/metadata.yaml)
- system.filesystem.inodes.usage (non-monotonic sum, unit {inodes}; attributes: device, mode, mountpoint, state, type; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/metadata.yaml)
- system.filesystem.limit (non-monotonic sum, unit By; attributes: system.device.name, system.filesystem.mode, system.filesystem.mountpoint, system.filesystem.type; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.filesystem.lock.count (non-monotonic sum, unit {lock}; attributes: file.lock.mechanism, file.lock.mode, file.lock.type, system.device.name; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.filesystem.usage (non-monotonic sum, unit By; attributes: device, mode, mountpoint, state, system.device.name, system.filesystem.mode, system.filesystem.mountpoint, system.filesystem.state, system.filesystem.type, type; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/metadata.yaml)
- system.filesystem.utilization (gauge, unit 1; attributes: device, mode, mountpoint, system.device.name, system.filesystem.mode, system.filesystem.mountpoint, system.filesystem.state, system.filesystem.type, type; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/metadata.yaml)
- system.linux.memory.available (non-monotonic sum, unit By; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.linux.memory.dirty (non-monotonic sum, unit By; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.limit (non-monotonic sum, unit By; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.available (non-monotonic sum, unit By; attributes: none; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.memory.linux.hugepages.limit (non-monotonic sum, unit {page}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.hugepages.page_size (non-monotonic sum, unit By; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.hugepages.reserved (non-monotonic sum, unit {page}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.hugepages.surplus (non-monotonic sum, unit {page}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.hugepages.usage (non-monotonic sum, unit {page}; attributes: system.memory.linux.hugepages.state; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.hugepages.utilization (gauge, unit 1; attributes: system.memory.linux.hugepages.state; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.shared (non-monotonic sum, unit By; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.linux.slab.usage (non-monotonic sum, unit By; attributes: system.memory.linux.slab.state; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.memory.page_size (gauge, unit By; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.usage (non-monotonic sum, unit By; attributes: state, system.memory.state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.memory.utilization (gauge, unit 1; attributes: state, system.memory.state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/metadata.yaml)
- system.network.connection.count (non-monotonic sum, unit {connection}; attributes: network.connection.state, network.interface.name, network.transport; in dataset; semantic-conventions/model/system/metrics.yaml)
- system.network.connections (non-monotonic sum, unit {connections}; attributes: protocol, state; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.conntrack.count (non-monotonic sum, unit {entries}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.conntrack.max (non-monotonic sum, unit {entries}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.dropped (monotonic sum, unit {packets}; attributes: device, direction; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.errors (monotonic sum, unit {errors}; attributes: device, direction, network.interface.name, network.io.direction; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.io (monotonic sum, unit By; attributes: device, direction, network.interface.name, network.io.direction; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.network.packet.count (monotonic sum, unit {packet}; attributes: network.io.direction, system.device.name; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.network.packet.dropped (monotonic sum, unit {packet}; attributes: network.interface.name, network.io.direction; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.network.packets (monotonic sum, unit {packets}; attributes: device, direction; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/networkscraper/metadata.yaml)
- system.paging.faults (monotonic sum, unit {faults}; attributes: system.paging.fault.type, type; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/pagingscraper/metadata.yaml)
- system.paging.operations (monotonic sum, unit {operations}; attributes: direction, system.paging.direction, system.paging.fault.type, type; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/pagingscraper/metadata.yaml)
- system.paging.usage (non-monotonic sum, unit By; attributes: device, state, system.device.name, system.paging.state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/pagingscraper/metadata.yaml)
- system.paging.utilization (gauge, unit 1; attributes: device, state, system.device.name, system.paging.state; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/pagingscraper/metadata.yaml)
- system.process.count (non-monotonic sum, unit {process}; attributes: process.state; in dataset; semantic-conventions/model/system/metrics.yaml)
- system.process.created (monotonic sum, unit {process}; attributes: none; in dataset; semantic-conventions/model/system/metrics.yaml)
- system.process.limit (non-monotonic sum, unit {thread}; attributes: none; not in dataset; semantic-conventions/model/system/metrics.yaml)
- system.processes.count (non-monotonic sum, unit {processes}; attributes: status; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/processesscraper/metadata.yaml)
- system.processes.created (monotonic sum, unit {processes}; attributes: none; not in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/processesscraper/metadata.yaml)
- system.uptime (gauge, unit s; attributes: none; in dataset; collector-contrib/receiver/hostmetricsreceiver/internal/scraper/systemscraper/metadata.yaml)
