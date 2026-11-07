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

Dashboard: `Docker - Overview` (`docker_daemon/assets/dashboards/docker_dashboard.json`), template variables: $scope (default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[0].definition.requests[0]', widget: 'timeseries: Running containers by image', queries: {q: 'sum:docker.containers.running{$scope} by {docker_image}.fill(0)'}, formulas: []}
- {source_path: 'widgets[1].definition.requests[0]', widget: 'toplist: Most RAM-intensive containers', queries: {q: 'top(avg:docker.mem.rss{$scope} by {container_name}, 5, ''max'', ''desc'')'}, formulas: []}
- {source_path: 'widgets[2].definition.requests[0]', widget: 'toplist: Most CPU-intensive containers', queries: {q: 'top(avg:docker.cpu.user{$scope} by {container_name}, 5, ''max'', ''desc'')'}, formulas: []}
- {source_path: 'widgets[3].definition.requests[0]', widget: 'heatmap: Memory by container', queries: {q: 'avg:docker.mem.rss{$scope} by {container_name}'}, formulas: []}
- {source_path: 'widgets[4].definition.requests[0]', widget: 'query_value: Running containers', queries: {q: 'sum:docker.containers.running{$scope}'}, formulas: []}
- {source_path: 'widgets[5].definition.requests[0]', widget: 'query_value: Stopped containers', queries: {q: 'sum:docker.containers.stopped{$scope}'}, formulas: []}
- {source_path: 'widgets[6].definition.requests[0]', widget: 'heatmap: CPU by container', queries: {q: 'avg:docker.cpu.user{$scope} by {container_name}'}, formulas: []}
- {source_path: 'widgets[7].definition.requests[0]', widget: 'timeseries: CPU user by image', queries: {q: 'avg:docker.cpu.user{$scope} by {docker_image}.fill(0)'}, formulas: []}
- {source_path: 'widgets[8].definition.requests[0]', widget: 'timeseries: RSS memory by image', queries: {q: 'avg:docker.mem.rss{$scope} by {docker_image}.fill(0)'}, formulas: []}
- {source_path: 'widgets[11].definition.requests[0]', widget: 'query_value: Running container change', queries: {q: '100*(sum:docker.containers.running{$scope}/timeshift(sum:docker.containers.running{$scope}, -300))'}, formulas: []}
- {source_path: 'widgets[12].definition.requests[0]', widget: 'timeseries: CPU system by image', queries: {q: 'avg:docker.cpu.system{$scope} by {docker_image}.fill(0)'}, formulas: []}
- {source_path: 'widgets[14].definition.requests[0]', widget: 'timeseries: Cache memory by image', queries: {q: 'sum:docker.mem.cache{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[18].definition.requests[0]', widget: 'timeseries: Swap by image', queries: {q: 'avg:docker.mem.swap{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[20].definition.requests[0]', widget: 'timeseries: Avg. I/O bytes read by image', queries: {q: 'avg:docker.io.read_bytes{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[21].definition.requests[0]', widget: 'timeseries: Avg. I/O bytes written by image', queries: {q: 'avg:docker.io.write_bytes{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[23].definition.requests[0]', widget: 'timeseries: Avg. rx bytes by image', queries: {q: 'avg:docker.net.bytes_rcvd{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[24].definition.requests[0]', widget: 'timeseries: Avg. tx bytes by image', queries: {q: 'avg:docker.net.bytes_sent{$scope} by {docker_image}'}, formulas: []}
- {source_path: 'widgets[25].definition.requests[0]', widget: 'toplist: Most tx-intensive containers', queries: {q: 'top(avg:docker.net.bytes_sent{$scope} by {container_name}, 5, ''max'', ''desc'')'}, formulas: []}
- {source_path: 'widgets[26].definition.requests[0]', widget: 'heatmap: tx by container', queries: {q: 'avg:docker.net.bytes_sent{$scope} by {container_name}'}, formulas: []}
- {source_path: 'widgets[27].definition.requests[0]', widget: 'toplist: Running containers by image', queries: {q: 'top(timeshift(sum:docker.containers.running{$scope} by {docker_image}.fill(60), 40), 20, ''last'', ''desc'')'}, formulas: []}
