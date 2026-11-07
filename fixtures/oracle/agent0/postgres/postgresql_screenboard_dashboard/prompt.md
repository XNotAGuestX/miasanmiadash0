Read-only task, do not create or change anything. Answer with one YAML code block only.

You are helping define expected test outcomes for migrating a Datadog dashboard to a Perses dashboard backed by the OpenTelemetry data in this Dash0 organization (dataset `default`). Use only metrics and labels that actually exist in this dataset (verify with the metric catalog and PromQL). Do not guess equivalences from similar names.

Dash0 PromQL conventions:
- Select a metric as `{otel_metric_name="<dotted.name>", otel_metric_type="<sum|gauge|histogram>"}`, with further matchers appended as `, <label>="<value>"`.
- Attribute keys become labels with dots replaced by `_`.
- Use `rate(<selector>[$__rate_interval])` for monotonic sums.
- Datadog template variables whose default is `*` are dropped (all series).

For every request below, answer with one YAML list item:
- source_path: <as given>
  outcome: translated | blocked
  promql: [<one PromQL string per displayed formula, in formula order>]   # translated only
  reason: <why blocked: no equivalent metric in this dataset / unsupported function / unit mismatch ...>
  otel_metrics: [<dotted OTel metric names you used>]
  labels: {<datadog tag>: <dash0 label>}
  live_check: <did the PromQL return series in the last 1h? yes/no, number of series>
  notes: <semantic caveats>

Rules: a request is all-or-nothing; if any formula cannot be expressed exactly, mark the whole request blocked. Never drop a series. Never invent a metric. Quote every YAML string value that contains a colon.

Note: receiver data in this dataset only arrived between about 14:05 and 15:21 UTC today, so run live checks over that window.

Dashboard: `Postgres - Overview` (`postgres/assets/dashboards/postgresql_screenboard_dashboard.json`), template variables: $scope (default `*`), $table (tag `table`, default `*`), $db (tag `db`, default `*`), $host (tag `host`, default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[1].definition.widgets[0].definition.requests[0]', widget: 'query_value: Max connections in use', queries: {query1: 'max:postgresql.percent_usage_connections{$scope,$host}'}, formulas: [query1 * 100]}
- {source_path: 'widgets[1].definition.widgets[1].definition.requests[0]', widget: 'query_value: Rows fetched / returned', queries: {query1: 'sum:postgresql.rows_fetched{$scope,$host}', query2: 'sum:postgresql.rows_returned{$scope,$host}'}, formulas: [query1 / (query1 + query2) * 100]}
- {source_path: 'widgets[2].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Dead rows', queries: {query1: 'sum:postgresql.dead_rows{$scope,$db,$table,$host}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[1].definition.requests[0]', widget: 'query_table: Resources by table', queries: {query1: 'avg:postgresql.total_size{$scope,$db,$table,$host} by {table}', query2: 'avg:postgresql.index_scans{$scope,$db,$table,$host} by {table}', query3: 'avg:postgresql.live_rows{$scope,$db,$table,$host} by {table}', query4: 'avg:postgresql.dead_rows{$scope,$db,$table,$host} by {table}'}, formulas: [query1, query2, query3, query4]}
- {source_path: 'widgets[2].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Temp bytes', queries: {query1: 'sum:postgresql.temp_bytes{$scope,$db,$table,$host}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[3].definition.requests[0]', widget: 'toplist: Most frequently scanned indexes', queries: {query1: 'avg:postgresql.index_scans{$scope,$db,$host} by {index}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[4].definition.requests[0]', widget: 'toplist: Least frequently scanned indexes', queries: {query1: 'avg:postgresql.index_scans{$scope,$db,$host} by {index}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[5].definition.requests[0]', widget: 'toplist: Tables with most disk usage (top 5)', queries: {query1: 'avg:postgresql.total_size{$scope,$table,$host} by {table}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[6].definition.requests[0]', widget: 'toplist: Tables with most live rows', queries: {query1: 'avg:postgresql.live_rows{$scope,$table,$host} by {table}'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Locks by lock mode', queries: {query1: 'sum:postgresql.locks{$scope,$host} by {lock_mode,table}'}, formulas: ['top(query1, 5, ''mean'', ''desc'')']}
- {source_path: 'widgets[3].definition.widgets[1].definition.requests[0]', widget: 'toplist: Locks by lock mode', queries: {query1: 'sum:postgresql.locks{$scope,$host} by {lock_mode,table}'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Deadlocks count', queries: {query1: 'max:postgresql.deadlocks.count{$scope,$host} by {db}.as_count()'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Inserted', queries: {query3: 'avg:postgresql.rows_inserted{$scope,$db,$host} by {db}'}, formulas: [query3]}
- {source_path: 'widgets[4].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Updated', queries: {query1: 'avg:postgresql.rows_updated{$scope,$db,$host} by {db}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[2].definition.requests[0]', widget: 'query_table: Actions', queries: {query1: 'avg:postgresql.rows_inserted{$db,$scope,$host} by {db}', query2: 'avg:postgresql.rows_updated{$db,$scope,$host} by {db}', query3: 'avg:postgresql.rows_deleted{$db,$scope,$host} by {db}'}, formulas: [query1, query2, query3]}
- {source_path: 'widgets[4].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Deleted', queries: {query2: 'avg:postgresql.rows_deleted{$scope,$db,$host} by {db}'}, formulas: [query2]}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Heap-only updates ', queries: {query1: 'avg:postgresql.rows_hot_updated{$scope,$db,$host} by {db}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Connections per database', queries: {query1: 'avg:postgresql.connections{$scope,$db,$host} by {db}.rollup(max)'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[0].definition.requests[1]', widget: 'timeseries: Connections per database', queries: {query1: 'min:postgresql.max_connections{$scope,$db,$host} by {db}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[1].definition.requests[0]', widget: 'toplist: Most connected databases', queries: {query1: 'max:postgresql.connections{$scope,$db,$host} by {db}'}, formulas: [query1]}
- {source_path: 'widgets[6].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Sequential scans vs index scans', queries: {query1: 'avg:postgresql.index_scans{$scope,$db,$host} by {db}', query2: 'avg:postgresql.seq_scans{$scope,$db,$host} by {db}'}, formulas: [query1, query2]}
- {source_path: 'widgets[6].definition.widgets[1].definition.requests[0]', widget: 'query_table: Top table scans', queries: {query1: 'avg:postgresql.index_scans{$scope,$db,$table,$host} by {db}', query2: 'avg:postgresql.seq_scans{$scope,$db,$table,$host} by {db}'}, formulas: [query1, query2]}
- {source_path: 'widgets[6].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Sequential scans vs. week before', queries: {query1: 'sum:postgresql.seq_scans{$scope,$db,$table,$host}'}, formulas: [query1]}
- {source_path: 'widgets[6].definition.widgets[2].definition.requests[1]', widget: 'timeseries: Sequential scans vs. week before', queries: {query1: 'sum:postgresql.seq_scans{$scope,$db,$table,$host}'}, formulas: [week_before(query1)]}
- {source_path: 'widgets[6].definition.widgets[3].definition.requests[0]', widget: 'toplist: Top function calls', queries: {query1: 'avg:postgresql.function.calls{$scope,$db,$table,$host} by {function}'}, formulas: [query1]}
- {source_path: 'widgets[7].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Number of hosts with replication delay', queries: {query1: 'sum:postgresql.replication_delay_bytes{$scope,$host} by {host}'}, formulas: [count_nonzero(query1)]}
- {source_path: 'widgets[7].definition.widgets[1].definition.requests[0]', widget: 'toplist: Max replication delay', queries: {query1: 'max:postgresql.replication_delay{$scope,$host} by {host}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Scheduled vs requested checkpoints', queries: {query1: 'sum:postgresql.bgwriter.checkpoints_timed{$scope,$db,$host}.as_count()', query2: 'sum:postgresql.bgwriter.checkpoints_requested{$scope,$db,$host}.as_count()'}, formulas: [query1, query2]}
- {source_path: 'widgets[8].definition.widgets[0].definition.requests[1]', widget: 'timeseries: Scheduled vs requested checkpoints', queries: {query1: 'sum:postgresql.bgwriter.checkpoints_requested{$scope,$db,$host}.as_count()'}, formulas: [query1]}
