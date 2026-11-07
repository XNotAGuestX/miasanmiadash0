#!/usr/bin/env bash
# Re-download the pinned DataDog/integrations-core fixtures (BSD-3-Clause).
# Usage: scripts/pin-integrations-core.sh   (needs an authenticated `gh`)
set -euo pipefail
SHA=a9b9e42b7e484861ecbd1f5919da7c52a694b74d
D=fixtures/datadog/integrations-core

fetch() {
  mkdir -p "$(dirname "$D/$2")"
  gh api "repos/DataDog/integrations-core/contents/$1?ref=$SHA" --jq .content | base64 -d > "$D/$2"
}

fetch postgres/assets/dashboards/postgresql_dashboard.json postgres/dashboards/postgresql_dashboard.json
fetch postgres/assets/dashboards/postgresql_screenboard_dashboard.json postgres/dashboards/postgresql_screenboard_dashboard.json
fetch postgres/assets/monitors/percent_usage_connections.json postgres/monitors/percent_usage_connections.json
fetch postgres/assets/monitors/replication_delay.json postgres/monitors/replication_delay.json
fetch kafka/assets/dashboards/kafka_dashboard.json kafka/dashboards/kafka_dashboard.json
fetch kafka/assets/monitors/kafka_offline_partition.json kafka/monitors/kafka_offline_partition.json
fetch kafka/assets/monitors/broker_produce_latency.json kafka/monitors/broker_produce_latency.json
fetch kafka/assets/monitors/kafka_high_producer_request_rate.json kafka/monitors/kafka_high_producer_request_rate.json
fetch docker_daemon/assets/dashboards/docker_dashboard.json docker_daemon/dashboards/docker_dashboard.json
fetch LICENSE LICENSE
