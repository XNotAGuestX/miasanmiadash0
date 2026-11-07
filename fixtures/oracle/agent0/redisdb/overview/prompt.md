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

Dashboard: `Redis - Overview` (`redisdb/assets/dashboards/overview.json`), template variables: $scope (default `*`), $host (tag `host`, default `*`), $key (tag `key`, default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[1].definition.widgets[0].definition.requests[0]', widget: 'query_value: Hit rate', queries: {query1: 'avg:redis.stats.keyspace_hits{$scope,$host}', query2: 'avg:redis.stats.keyspace_misses{$scope,$host}'}, formulas: [(query1 / (query1 + query2)) * 100]}
- {source_path: 'widgets[1].definition.widgets[1].definition.requests[0]', widget: 'query_value: Blocked clients', queries: {query1: 'sum:redis.clients.blocked{$scope,$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[2].definition.requests[0]', widget: 'query_value: Redis keyspace', queries: {query1: 'sum:redis.keys{$scope,$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[3].definition.requests[0]', widget: 'query_value: Unsaved changes', queries: {query1: 'sum:redis.rdb.changes_since_last{$scope,$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[4].definition.requests[0]', widget: 'query_value: Primary link down', queries: {query1: 'sum:redis.replication.master_link_down_since_seconds{$scope,$host}'}, formulas: []}
- {source_path: 'widgets[2].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Latency by Host', queries: {query2: 'avg:redis.info.latency_ms{$scope,$host} by {host}'}, formulas: [query2]}
- {source_path: 'widgets[2].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Slowlog duration', queries: {query1: 'sum:redis.slowlog.micros.95percentile{$scope,$host} by {name,command}'}, formulas: ['top(query1 / 1000, 10, ''mean'', ''desc'')']}
- {source_path: 'widgets[2].definition.widgets[3].definition.requests[0]', widget: 'toplist: Slowlog query rates', queries: {query1: 'sum:redis.slowlog.micros.count{$host,$scope} by {command,name}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Average replication delay (offset)', queries: {query1: 'avg:redis.replication.delay{$host,$scope}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.widgets[5].definition.requests[0]', widget: 'timeseries: Average CPU usage', queries: {query1: 'avg:redis.cpu.sys{$host,$scope}', query2: 'avg:redis.cpu.user{$host,$scope}'}, formulas: [query1, query2]}
- {source_path: 'widgets[2].definition.widgets[6].definition.requests[0]', widget: 'query_value: Cache hit rate', queries: {query1: 'avg:redis.stats.keyspace_hits{$scope,$host}', query2: 'avg:redis.stats.keyspace_misses{$scope,$host}'}, formulas: [(query1 / (query1 + query2)) * 100]}
- {source_path: 'widgets[2].definition.widgets[7].definition.requests[0]', widget: 'timeseries: Cache hit rate', queries: {query1: 'avg:redis.stats.keyspace_hits{$scope,$host}', query2: 'avg:redis.stats.keyspace_misses{$scope,$host}'}, formulas: [(query1 / (query1 + query2)) * 100]}
- {source_path: 'widgets[3].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Percent Used Memory by Host', queries: {query1: 'avg:redis.mem.used{$scope,$host} by {host}', query2: 'max:redis.mem.maxmemory{$scope,$host} by {host}'}, formulas: [(query1 / query2) * 100]}
- {source_path: 'widgets[3].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Evictions', queries: {query2: 'sum:redis.keys.evicted{$scope,$host} by {host}'}, formulas: [per_minute(query2)]}
- {source_path: 'widgets[3].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Total allocated memory', queries: {query1: 'sum:redis.mem.rss{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[4].definition.requests[0]', widget: 'query_value: Fragmentation ratio', queries: {query1: 'avg:redis.mem.fragmentation_ratio{$scope,$host}'}, formulas: []}
- {source_path: 'widgets[3].definition.widgets[5].definition.requests[0]', widget: 'timeseries: Fragmentation ratio', queries: {query1: 'avg:redis.mem.fragmentation_ratio{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Connected clients', queries: {query1: 'sum:redis.net.clients{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Blocked clients', queries: {query2: 'sum:redis.clients.blocked{$scope,$host}'}, formulas: [query2]}
- {source_path: 'widgets[4].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Connected replicas', queries: {query1: 'sum:redis.net.slaves{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Rejected connections', queries: {query1: 'sum:redis.net.rejected{$scope,$host}'}, formulas: [diff(query1)]}
- {source_path: 'widgets[4].definition.widgets[5].definition.requests[0]', widget: 'query_value: Commands per second', queries: {query1: 'sum:redis.net.commands{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Total keys', queries: {query1: 'sum:redis.keys{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[1].definition.requests[0]', widget: 'query_value: Current total', queries: {query1: 'sum:redis.keys{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Expired keys', queries: {query1: 'sum:redis.keys.expired{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[4].definition.requests[0]', widget: 'query_value: Keys with expiration', queries: {query1: 'sum:redis.expires{$scope,$host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[5].definition.requests[0]', widget: 'distribution: Key length distribution', queries: {query1: 'sum:redis.key.length{$scope, $host, $key} by {key}'}, formulas: [query1]}
- {source_path: 'widgets[6].definition.widgets[0].definition.requests[0]', widget: 'list_stream: Error Logs', queries: {}, formulas: []}
- {source_path: 'widgets[6].definition.widgets[1].definition.requests[0]', widget: 'list_stream: All Logs', queries: {}, formulas: []}
