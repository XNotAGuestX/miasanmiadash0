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

Dashboard: `Postgres - Metrics` (`postgres/assets/dashboards/postgresql_dashboard.json`), template variables: $scope (default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[0].definition.requests[0]', widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_fetched{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[0].definition.requests[1]', widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_returned{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[0].definition.requests[2]', widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_inserted{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[0].definition.requests[3]', widget: 'timeseries: Rows fetched / returned / inserted / updated (per sec)', queries: {query1: 'avg:postgresql.rows_updated{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[1].definition.requests[0]', widget: 'timeseries: Connections', queries: {query1: 'avg:postgresql.connections{$scope} by {db}'}, formulas: [query1]}
- {source_path: 'widgets[2].definition.requests[0]', widget: 'timeseries: Inserts / updates / deletes (per sec)', queries: {query1: 'postgresql.rows_inserted{$scope}', query2: 'postgresql.rows_deleted{$scope}', query3: 'postgresql.rows_updated{$scope}'}, formulas: [query1, query2, query3]}
- {source_path: 'widgets[3].definition.requests[0]', widget: 'timeseries: Disk utilization (%)', queries: {query1: 'avg:system.io.util{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.requests[0]', widget: 'timeseries: System load', queries: {query1: 'system.load.1{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.requests[1]', widget: 'timeseries: System load', queries: {query1: 'system.load.5{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.requests[2]', widget: 'timeseries: System load', queries: {query1: 'system.load.15{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.requests[0]', widget: 'timeseries: CPU usage (%)', queries: {query1: 'system.cpu.idle{$scope}', query2: 'system.cpu.system{$scope}', query3: 'system.cpu.iowait{$scope}', query4: 'system.cpu.user{$scope}', query5: 'system.cpu.stolen{$scope}', query6: 'system.cpu.guest{$scope}'}, formulas: [query1, query2, query3, query4, query5, query6]}
- {source_path: 'widgets[6].definition.requests[0]', widget: 'timeseries: I/O wait (%)', queries: {query1: 'max:system.cpu.iowait{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[7].definition.requests[0]', widget: 'timeseries: System memory', queries: {query1: 'sum:system.mem.usable{$scope}', query2: 'sum:system.mem.total{$scope}'}, formulas: [query1, query2 - query1]}
- {source_path: 'widgets[8].definition.requests[0]', widget: 'timeseries: Network traffic (per sec)', queries: {query1: 'sum:system.net.bytes_rcvd{$scope}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.requests[1]', widget: 'timeseries: Network traffic (per sec)', queries: {query1: 'sum:system.net.bytes_sent{$scope}'}, formulas: [query1]}
