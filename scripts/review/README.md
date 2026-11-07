# Local Perses viewer: converter output and oracle review dashboards

## View converter output

Start Perses (step 2 below), then load any `migrator convert --out` directory. Nothing is sent to Dash0
except the dashboards' own PromQL queries, through the local datasource proxy:

```sh
uv run migrator convert --source datadog --input fixtures/datadog/integrations-core/postgres \
  --mapping mappings/datadog/postgres.json --out out/convert/postgres
uv run scripts/review/load_local.py out/convert/postgres --perses-url http://localhost:8080
```

The script creates project `datadog-migration` with the same `dash0` Secret and datasource, loads
each dashboard, verifies the read-back and prints its URL. The rest of this file describes the oracle
review dashboards, which load the same way.

# Oracle review dashboards (issue #87)

Development-time aid for humans reviewing the agent0-derived expectations in
`fixtures/expected/<svc>/<id>/expected.yaml`. The dashboards show the oracle's PromQL, not converter
output. Triage colours are signals only; approval is still `reviewed: true` in `overrides.yaml`.

## 1. Render

```sh
uv run scripts/render_review_dashboard.py postgres/postgresql_dashboard   # or --all
```

This writes `out/oracle-review/<svc>/<id>/` (git-ignored), a run directory in the format
`migrator publish` reads: `manifest.json` plus `dashboards/oracle-review-<svc>-<id>.json`. Each
dashboard has one panel per translated request, titled `[<priority>] <widget> · <source_path>`. The
panel description holds the Datadog queries, agent0's notes and the triage signals. A Markdown panel
at the end lists the blocked requests.

## 2. Start a local Perses (v0.55.1)

```sh
export DASH0_AUTH_TOKEN=...      # required by compose; never commit it
export DASH0_API_URL=https://api.eu-west-1.aws.dash0.com   # optional, this is the default
export DASH0_DATASET=default     # optional, this is the default
docker compose -f scripts/review/docker-compose.yaml up -d   # PERSES_PORT=18080 if 8080 is taken
```

Provisioning creates project `oracle-review`, a `dash0` Secret and the project's default Prometheus
datasource. The datasource proxies to `$DASH0_API_URL/api/prometheus` with the header
`Dash0-Dataset: $DASH0_DATASET`. The token reaches the container only as the compose secret file
`/run/secrets/dash0_auth_token`, which the Secret reads through `credentialsFile`. Without a real
token, Perses and the dashboards still load, but every query returns Dash0's 401 ("The provided auth
token is not known."). To start without a token, set any placeholder value.

## 3. Load and open

```sh
uv run scripts/review/load_local.py --perses-url http://localhost:8080   # every run dir under out/oracle-review
```

The script creates the project, secret and datasource if they are missing, then POSTs each dashboard
(or PUTs it if it already exists). It reads each dashboard back and checks it is unchanged. Perses
drops empty fields such as `variables: []` on read, so those don't count as changes. Finally it
prints the URL of each dashboard with the review window already set,
`?start=1794060300000&end=1794064860000`, which is 2026-11-07 14:05–15:21 UTC. That is the only
window with receiver data in the Dash0 `default` dataset.

Stop and discard everything with `docker compose -f scripts/review/docker-compose.yaml down -v`.

## Fallback: review in Dash0 itself

Use this only after PR #81 (`migrator publish`) has merged:

```sh
uv run migrator publish out/oracle-review/<svc>/<id>
```

Publish into the **demo** dataset. The `oracle-review-` name prefix keeps these dashboards apart
from converter output. This is a live write: it needs Felix's approval first. Label the issue
`needs:approval` and link the approval there.
