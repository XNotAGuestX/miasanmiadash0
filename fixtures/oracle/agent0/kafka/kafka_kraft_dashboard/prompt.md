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

Dashboard: `Kafka KRaft Overview` (`kafka/assets/dashboards/kafka_kraft_dashboard.json`), template variables: $env (tag `env`, default `*`), $consumer_group (tag `consumer_group`, default `*`), $topic (tag `topic`, default `*`). A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs).

Requests:
- {source_path: 'widgets[2].definition.widgets[1].definition.requests[0]', widget: 'topology_map: Kafka Topology for $topic, $env', queries: {}, formulas: []}
- {source_path: 'widgets[2].definition.widgets[2].definition.requests[0]', widget: 'query_table: Topic Health', queries: {query1: 'count:data_streams.latency{type:kafka AND direction:out AND (pathway_type:edge OR pathway_type:partial_edge) AND $topic AND $env} by {topic,env}.as_rate()', query2: 'count:data_streams.latency{type:kafka AND direction:in AND (pathway_type:edge OR pathway_type:partial_edge) AND $topic AND $env} by {topic,env}.as_rate()', query3: 'max:data_streams.kafka.lag_seconds{$topic,$env} by {topic,env}'}, formulas: [query1, query2, query3]}
- {source_path: 'widgets[3].definition.widgets[0].definition.requests[0]', widget: 'query_value: Offline Partitions', queries: {query1: 'sum:kafka.replication.offline_partitions_count{*}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[1].definition.requests[0]', widget: 'query_value: Under Replicated Partitions', queries: {query1: 'sum:kafka.replication.under_replicated_partitions{$env}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[2].definition.requests[0]', widget: 'query_value: ISR Delta', queries: {query1: 'max:kafka.replication.isr_expands.rate{$env}', query2: 'max:kafka.replication.isr_shrinks.rate{$env}'}, formulas: [query1 - query2]}
- {source_path: 'widgets[3].definition.widgets[3].definition.requests[0]', widget: 'query_value: Follower Fetch Latency', queries: {query1: 'avg:kafka.request.fetch_follower.time.avg{$env}'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[4].definition.requests[0]', widget: 'query_value: Consumer Fetch Latency', queries: {query1: 'avg:kafka.request.fetch_consumer.time.avg{$env}'}, formulas: [query1]}
- {source_path: 'widgets[3].definition.widgets[5].definition.requests[0]', widget: 'query_value: Produce Latency', queries: {query1: 'avg:kafka.request.produce.time.avg{$env}'}, formulas: [query1]}
- {source_path: 'widgets[4].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Clean and Unclean Leader Elections', queries: {query2: 'avg:kafka.replication.leader_elections.rate{$env}', query1: 'avg:kafka.replication.unclean_leader_elections.rate{$env}'}, formulas: [query2, query1]}
- {source_path: 'widgets[4].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Broker Network Throughput', queries: {query1: 'sum:kafka.net.bytes_in.rate{$env} by {env}.weighted()', query2: 'sum:kafka.net.bytes_out.rate{$env} by {env}.weighted()'}, formulas: [query1, query2]}
- {source_path: 'widgets[4].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Producer and Fetch Request Purgatory ', queries: {query1: 'sum:kafka.request.producer_request_purgatory.size{$env} by {env}.weighted()', query2: 'sum:kafka.request.fetch_request_purgatory.size{$env} by {env}.weighted()'}, formulas: [query1, query2]}
- {source_path: 'widgets[4].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Request Times', queries: {query1: 'avg:kafka.request.produce.time.avg{$env} by {env}', query2: 'avg:kafka.request.fetch_consumer.time.avg{$env} by {env}'}, formulas: [query1, query2]}
- {source_path: 'widgets[5].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Bytes Out by Topic', queries: {query1: 'sum:kafka.producer.bytes_out{$env} by {topic,env}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Request and Response Rate', queries: {query1: 'sum:kafka.producer.request_rate{$env} by {host}.weighted()', query2: 'sum:kafka.producer.response_rate{$env} by {host}.weighted()'}, formulas: [abs(query1), abs(query2)]}
- {source_path: 'widgets[5].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Average Request Latency', queries: {query1: 'sum:kafka.producer.request_latency_avg{$env} by {env}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[5].definition.widgets[4].definition.requests[0]', widget: 'timeseries: I/O Wait Time', queries: {query1: 'sum:kafka.producer.io_wait{$env} by {env}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[6].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Consumer Lag by Group', queries: {query1: 'sum:kafka.consumer_lag{$env,$consumer_group} by {host,consumer_group,env}', query2: 'sum:kafka.consumer_offset{$env,$consumer_group} by {host,consumer_group,env}'}, formulas: [query1, query2]}
- {source_path: 'widgets[6].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Bytes Consumed', queries: {query1: 'sum:kafka.consumer.bytes_in{$env,$consumer_group} by {consumer_group,env}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[6].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Messages Consumed', queries: {query1: 'sum:kafka.consumer.messages_in{$env,$consumer_group} by {client-id,env}.weighted()'}, formulas: [abs(query1)]}
- {source_path: 'widgets[6].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Min Fetch Rate', queries: {query1: 'sum:kafka.consumer.fetch_rate{$env,$consumer_group} by {env,consumer_group}.weighted()'}, formulas: [query1]}
- {source_path: 'widgets[7].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Top 10 Max Kafka Lag by env', queries: {query1: 'max:data_streams.kafka.lag_seconds{$topic ,$env} by {env,topic}'}, formulas: ['top(query1, 10, ''max'', ''desc'')']}
- {source_path: 'widgets[7].definition.widgets[2].definition.requests[0]', widget: 'timeseries: Incoming messages by env, producing service for $topic', queries: {upstream_services_throughput: 'count(v: v>=0):data_streams.latency{direction:out,pathway_type:full,type:kafka,$topic,$env} by {service,env}.as_rate().rollup(10)'}, formulas: [default_zero(upstream_services_throughput)]}
- {source_path: 'widgets[7].definition.widgets[3].definition.requests[0]', widget: 'timeseries: Outgoing messages by env, consuming service for $topic', queries: {downstream_services_throughput_by_queues: 'count(v: v>=0):data_streams.latency{direction:in,pathway_type:full,type:kafka,$topic,$env} by {service,env}.as_rate().rollup(10)'}, formulas: [default_zero(downstream_services_throughput_by_queues)]}
- {source_path: 'widgets[7].definition.widgets[4].definition.requests[0]', widget: 'timeseries: Top 10 p95 message size by env for $topic', queries: {query1: 'p95:data_streams.payload_size{type:kafka,$topic,$env} by {topic,env}'}, formulas: ['top(query1, 10, ''mean'', ''desc'')']}
- {source_path: 'widgets[7].definition.widgets[5].definition.requests[0]', widget: 'distribution: Distribution of message size for $topic', queries: {}, formulas: []}
- {source_path: 'widgets[8].definition.widgets[1].definition.requests[0]', widget: 'query_value: Current Leader', queries: {query1: 'avg:kafka.kraft.current_leader{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[2].definition.requests[0]', widget: 'query_value: Controller ID', queries: {query1: 'avg:kafka.kraft.metadata_loader.current_controller_id{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[3].definition.requests[0]', widget: 'query_value: Active Brokers', queries: {query1: 'avg:kafka.controller.active_broker_count{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[4].definition.requests[0]', widget: 'query_value: Fenced Brokers', queries: {query1: 'avg:kafka.controller.fenced_broker_count{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[5].definition.requests[0]', widget: 'query_value: High Watermark', queries: {query1: 'avg:kafka.kraft.high_watermark{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[6].definition.requests[0]', widget: 'query_value: Metadata Version', queries: {query1: 'avg:kafka.kraft.metadata_loader.current_metadata_version{$env}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[7].definition.requests[0]', widget: 'timeseries: Metadata Replication Lag', queries: {query1: 'avg:kafka.kraft.broker_metadata.last_applied_record_lag_ms{$env} by {host}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[8].definition.requests[0]', widget: 'timeseries: Raft Commit Latency', queries: {query1: 'avg:kafka.kraft.commit_latency_avg{$env} by {host}', query2: 'avg:kafka.kraft.commit_latency_max{$env} by {host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[8].definition.widgets[9].definition.requests[0]', widget: 'timeseries: Raft Records Rate', queries: {query1: 'avg:kafka.kraft.append_records_rate{$env} by {host}', query2: 'avg:kafka.kraft.fetch_records_rate{$env} by {host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[8].definition.widgets[10].definition.requests[0]', widget: 'timeseries: Metadata Errors', queries: {query1: 'sum:kafka.kraft.broker_metadata.metadata_load_error_count{$env} by {host}', query2: 'sum:kafka.kraft.broker_metadata.metadata_apply_error_count{$env} by {host}'}, formulas: [query1, query2]}
- {source_path: 'widgets[8].definition.widgets[11].definition.requests[0]', widget: 'timeseries: Snapshot Age', queries: {query1: 'avg:kafka.kraft.snapshot_emitter.latest_snapshot_generated_age_ms{$env} by {host}'}, formulas: [query1]}
- {source_path: 'widgets[8].definition.widgets[12].definition.requests[0]', widget: 'timeseries: Poll Idle Ratio', queries: {query1: 'avg:kafka.kraft.poll_idle_ratio_avg{$env} by {host}'}, formulas: [query1]}
- {source_path: 'widgets[9].definition.widgets[1].definition.requests[0]', widget: 'timeseries: JVM GC Count by Type', queries: {query1: 'sum:jvm.gc.major_collection_count{$env} by {type,env}.weighted()', query2: 'sum:jvm.gc.minor_collection_count{$env} by {type,env}.weighted()'}, formulas: [query1, query2]}
- {source_path: 'widgets[9].definition.widgets[2].definition.requests[0]', widget: 'timeseries: JVM GC Time by Type', queries: {query1: 'sum:jvm.gc.major_collection_time{$env} by {type,env}.weighted()', query2: 'sum:jvm.gc.minor_collection_time{$env} by {type,env}.weighted()'}, formulas: [query1, query2]}
- {source_path: 'widgets[10].definition.widgets[1].definition.requests[0]', widget: 'timeseries: Count per Log Status', queries: {a: null}, formulas: [a]}
- {source_path: 'widgets[10].definition.widgets[2].definition.requests[0]', widget: 'list_stream: Error Logs', queries: {}, formulas: []}
