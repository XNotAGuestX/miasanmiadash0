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

Dashboard: `NGINX - Metrics` (`nginx/assets/dashboards/NGINX-Metrics_dashboard.json`), template variables: $scope (default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[0].definition.requests[0]', widget: 'timeseries: Dropped connections per second', queries: {q: 'sum:nginx.net.conn_dropped_per_s{$scope}'}, formulas: []}
- {source_path: 'widgets[1].definition.requests[0]', widget: 'timeseries: 5xx per second (only available for NGINX Plus)', queries: {q: 'sum:nginx.server_zone.responses.5xx{$scope}'}, formulas: []}
- {source_path: 'widgets[2].definition.requests[0]', widget: 'timeseries: Requests per second', queries: {q: 'sum:nginx.net.request_per_s{$scope}'}, formulas: []}
- {source_path: 'widgets[3].definition.requests[0]', widget: 'timeseries: Active connections per second', queries: {q: 'sum:nginx.net.connections{$scope}'}, formulas: []}
- {source_path: 'widgets[4].definition.requests[0]', widget: 'timeseries: Connections: reading,writing,waiting', queries: {q: 'sum:nginx.net.reading{$scope}'}, formulas: []}
- {source_path: 'widgets[4].definition.requests[1]', widget: 'timeseries: Connections: reading,writing,waiting', queries: {q: 'sum:nginx.net.writing{$scope}'}, formulas: []}
- {source_path: 'widgets[4].definition.requests[2]', widget: 'timeseries: Connections: reading,writing,waiting', queries: {q: 'sum:nginx.net.waiting{$scope}'}, formulas: []}
