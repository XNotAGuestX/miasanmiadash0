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

Dashboard: `NGINX - Overview` (`nginx/assets/dashboards/NGINX-Overview_dashboard.json`), template variables: $Host (tag `host`, default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[1].definition.widgets[0].definition.requests[0]', widget: 'query_value: Dropped connections, last 15m', queries: {q: 'sum:nginx.net.conn_dropped_per_s{*}.as_count()'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[0]', widget: 'query_value: Requests per second', queries: {query1: 'avg:nginx.net.request_per_s{*}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[1].definition.requests.fill', widget: 'hostmap: Requests per second by host', queries: {q: 'avg:nginx.net.request_per_s{*} by {host}'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Requests: reading, writing, waiting', queries: {query1: 'sum:nginx.net.reading{$Host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[1]', widget: 'timeseries: Requests: reading, writing, waiting', queries: {query1: 'sum:nginx.net.writing{$Host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[2]', widget: 'timeseries: Requests: reading, writing, waiting', queries: {query1: 'sum:nginx.net.waiting{$Host}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[5].definition.requests[0]', widget: 'change: Change in overall requests per second', queries: {q: 'sum:nginx.net.request_per_s{*} by {service}'}, formulas: []}
- {source_path: 'widgets[5].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Dropped connections per second', queries: {query1: 'sum:nginx.net.conn_dropped_per_s{$Host}'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Active connections per second', queries: {query1: 'sum:nginx.net.connections{$Host}'}, formulas: [query1]}
