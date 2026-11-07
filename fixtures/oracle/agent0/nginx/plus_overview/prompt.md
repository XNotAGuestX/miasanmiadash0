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

Dashboard: `NGINX Plus - Overview` (`nginx/assets/dashboards/plus_overview.json`), template variables: $host (tag `host`, default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[1].definition.widgets[1].definition.requests[0]', widget: 'query_value: Accepted connections', queries: {q: 'sum:nginx.connections.accepted{$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[2].definition.requests[0]', widget: 'query_value: Active connections', queries: {q: 'sum:nginx.connections.active{$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[3].definition.requests[0]', widget: 'query_value: Idle/waiting connections', queries: {q: 'sum:nginx.connections.idle{$host}'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[4].definition.requests[0]', widget: 'query_value: Dropped connections', queries: {q: 'per_second(sum:nginx.connections.dropped{$host})'}, formulas: []}
- {source_path: 'widgets[1].definition.widgets[5].definition.requests[0]', widget: 'query_value: Total requests', queries: {q: 'sum:nginx.requests.total{$host}'}, formulas: []}
- {source_path: 'widgets[3].definition.widgets[0].definition.requests.fill', widget: 'hostmap: Request load by host', queries: {q: 'avg:nginx.requests.current{$host} by {host}'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[0]', widget: 'query_table: 4xx & 5xx responses per sec', queries: {q: 'avg:nginx.server_zone.responses.total{$host} by {host}'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[1]', widget: 'query_table: 4xx & 5xx responses per sec', queries: {q: 'avg:nginx.server_zone.responses.4xx{$host} by {host}'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[0].definition.requests[2]', widget: 'query_table: 4xx & 5xx responses per sec', queries: {q: 'avg:nginx.server_zone.responses.5xx{$host} by {host}'}, formulas: []}
- {source_path: 'widgets[4].definition.widgets[1].definition.requests[0]', widget: 'timeseries: 4xx & 5xx responses per sec', queries: {query1: 'sum:nginx.server_zone.responses.4xx{$host} by {host}', query2: 'sum:nginx.server_zone.responses.5xx{$host} by {host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[5].definition.widgets[0].definition.requests[0]', widget: 'query_value: Avg bytes hit', queries: {q: 'avg:nginx.cache.hit.bytes{$host}'}, formulas: []}
- {source_path: 'widgets[5].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Bytes hit in cache', queries: {query1: 'sum:nginx.cache.hit.bytes{$host}'}, formulas: []}
- {source_path: 'widgets[5].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Bypassed bytes in cached', queries: {query1: 'sum:nginx.cache.bypass.bytes{$host}', query2: 'sum:nginx.cache.bypass.bytes_written{$host}'}, formulas: [query1, query2, query1 + query2]}
- {source_path: 'widgets[5].definition.widgets[3].definition.requests[0]', widget: 'query_value: Hosts loading cache', queries: {q: 'sum:nginx.cache.cold{$host}'}, formulas: []}
- {source_path: 'widgets[5].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Cache size', queries: {query1: 'sum:nginx.cache.max_size{$host}', query2: 'sum:nginx.cache.size{$host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[5].definition.widgets[5].definition.requests[0]', widget: 'timeseries: Missed bytes in cache', queries: {query1: 'sum:nginx.cache.miss.bytes{$host}', query2: 'sum:nginx.cache.miss.bytes_written{$host}'}, formulas: [query1, query2, query1 + query2]}
- {source_path: 'widgets[6].definition.widgets[0].definition.requests[0]', widget: 'timeseries: Current connections (idle & active)', queries: {query1: 'sum:nginx.connections.active{$host}', query2: 'sum:nginx.connections.idle{$host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[6].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Dropped connections per second', queries: {query1: 'sum:nginx.connections.dropped{$host}'}, formulas: [per_second(query1)]}
- {source_path: 'widgets[7].definition.widgets[0].definition.requests[0]', widget: 'query_table: Handshakes per hosts', queries: {q: 'sum:nginx.ssl.handshakes_count{*} by {host}.as_count()'}, formulas: []}
- {source_path: 'widgets[7].definition.widgets[0].definition.requests[1]', widget: 'query_table: Handshakes per hosts', queries: {q: 'sum:nginx.ssl.handshakes_failed_count{*} by {host}.as_count()'}, formulas: []}
- {source_path: 'widgets[7].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Successful vs failed SSL handshakes', queries: {query1: 'sum:nginx.ssl.handshakes_count{$host} by {host}.as_count()'}, formulas: [query1]}
- {source_path: 'widgets[7].definition.widgets[1].definition.requests[1]', widget: 'timeseries: Successful vs failed SSL handshakes', queries: {q: '-sum:nginx.ssl.handshakes_failed_count{*} by {host}.as_count()'}, formulas: []}
