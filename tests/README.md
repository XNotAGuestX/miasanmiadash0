# Unit tests (pytest)

Test-first suite for the deterministic Datadog → Perses (Dash0 PromQL) converter. It is written
before the engine exists: today every test fails red with `ModuleNotFoundError: No module named
'migrator.source'`. A case turns green when the converter implements the interface below and
produces exactly the expected outcome.

No LLM takes part in conversion (`AGENTS.md`). Agent0 was used **only at development time** to
*propose* expected outcomes. Its answers are frozen as provenance, never read by a test, and every
expectation must be confirmed by a human before it counts (see "Review").

## Run

```bash
uv sync                                  # once: uv-managed Python 3.11 + locked deps (uv.lock)
uv run pytest                            # reviewed cases only; unreviewed ones are skipped
uv run pytest --include-unreviewed       # also run oracle-proposed, not yet reviewed cases
uv run pytest -m p0                      # only the MVP cases (also: -m p1, -m p2)
uv run pytest tests/unit/requests        # only request/widget/parser tests
uv run pytest tests/scripts              # oracle runner (scripts/run_oracle.py)
```

Tests are offline: an autouse fixture in `conftest.py` replaces `socket.socket` and
`socket.create_connection`, so any network access raises.

## Layout

| Path | Level | Cases come from |
|---|---|---|
| `unit/requests/test_parse_query.py` | one Datadog metric query string | `fixtures/synthetic/queries.yaml` (hand-written from plan 02) + every metric query in the pinned dashboards (totality corpus) |
| `unit/requests/test_request.py` | one request (`queries` + `formulas`) → PromQL or a blocking diagnostic | `fixtures/expected/*/*/expected.yaml` → `requests:` |
| `unit/requests/test_widget.py` | one widget → one Perses panel, or blocked | `expected.yaml` → `widgets:` |
| `unit/dashboards/test_dashboards.py` | a whole dashboard → Perses dashboard + per-widget outcomes | `expected.yaml` → `dashboard:` |
| `support.py` | shared helpers: case loading, source-path resolution, PromQL canonicalization, diagnostics checks | |
| `conftest.py` | `--include-unreviewed` option, `unreviewed` skip, no-network guard | |

## Interfaces under test

All from `migrator.source.datadog` (layout: `docs/handoff/00-context.md` §4). Results are
dataclasses; tests convert them to plain dicts with `support.as_plain`, so field names matter and
class names do not.

```python
parse_metric_query(text: str) -> ParseResult
#   ParseResult: ok: bool, query: MetricQuery | None, code: str | None, offset: int | None, message: str | None
#   MetricQuery: aggregator, metric, filters[{kind, key, value} | {kind, name}], group_by: list[str], functions[{name, args}]
#   A failed parse has code UNSUPPORTED_QUERY_SYNTAX or UNSUPPORTED_QUERY_FUNCTION and 0 <= offset <= len(text).

load_mapping(path) -> Mapping                          # mappings/datadog/<service>.json

translate_request(request: dict, *, mapping, variables: list[dict], source_path: str) -> RequestResult
#   RequestResult: outcome ("translated" | "blocked"), queries: list[str] (PromQL, one per displayed formula),
#                  diagnostics: list[Diagnostic]
#   Diagnostic: code, severity, source_id, source_path, message, suggested_action, source_text

translate_widget(widget: dict, *, mapping, variables: list[dict], source_path: str) -> WidgetResult
#   WidgetResult: outcome, panel_key ("widget-<i>" or group child "widget-<i>-<j>"), panel (Perses Panel | None), diagnostics

translate_dashboard(dashboard: dict, *, mapping, project: str) -> DashboardResult
#   DashboardResult: outcome ("translated" | "partial" | "blocked"), dashboard (Perses Dashboard | None),
#                    widgets: list[WidgetResult] (one per leaf widget, source order), diagnostics
```

What the tests assert:

- **Request:** outcome; for `translated`, the PromQL list equals the expected list after
  canonicalization (`support.canonical_promql`: ignores whitespace, redundant parentheses, matcher
  order, `by`/`without` label order and `+`/`*` operand order; different metrics, functions,
  matchers or aggregations never compare equal); a blocked request emits no queries; error codes
  exact, warning codes exact for translated requests; every diagnostic's `source_path` lies inside
  the request.
- **Widget:** all-or-nothing (never drop a series); panel key, title, Perses panel plugin
  (`TimeSeriesChart`, `StatChart`, `Markdown`), only `TimeSeriesQuery` queries, PromQL as above.
- **Dashboard:** dashboard outcome and the ordered per-widget outcomes; exactly the translated
  widgets become panels with their PromQL; structure invariants (kind, project, slug name, no
  `dash0Extensions` id, panel keys, every layout item references a panel, grid width ≤ 24);
  byte-identical output on a second run (determinism).
- **Parser:** spec cases (subset match); every real corpus query parses or yields exactly one of
  the two parse codes, never a prefix match; deterministic.

## Case format (`fixtures/expected/<service>/<dashboard>/expected.yaml`)

Generated by `scripts/build_expected.py`; do not edit by hand. Inputs are **not** duplicated:
each case names a `source_path` that is resolved inside the pinned source dashboard
(`source_fixture`).

```yaml
source_fixture: fixtures/datadog/integrations-core/nginx/dashboards/NGINX-Metrics_dashboard.json
mapping: mappings/datadog/nginx.json      # reviewed mapping the expectation assumes (end state)
project: datadog-migration
requests:
- source_path: widgets[0].definition.requests[0]
  milestone: p2                           # p0 MVP (plans 01-04), p1 plan 05, p2 plan 08 services
  reviewed: false                         # false -> skipped unless --include-unreviewed
  provenance: {kind: agent0 | human, ref: <file>}
  live_check: {agent0: <did Agent0's PromQL return data in Dash0>}
  dataset:                                # optional fixture metadata, never compared to converter output
    available: false                      # OTel metric is defined but absent from the Dash0 `default` dataset
    missing_metrics: [zookeeper.connection.active]
    otel_sources: [collector-contrib/receiver/zookeeperreceiver/metadata.yaml]
  expected:
    outcome: translated | blocked
    promql: [...]                         # translated only
    errors: [...]                         # e.g. MISSING_METRIC_MAPPING, UNSUPPORTED_FORMULA,
                                          #      UNSUPPORTED_QUERY_FUNCTION, UNSUPPORTED_DATA_SOURCE
    warnings: [...]                       # e.g. TEMPLATE_VARIABLE_DROPPED, DEFAULT_AGGREGATOR_APPLIED
  notes: [...]                            # optional, e.g. rule overlay applied
widgets:   [{source_path, type, milestone, reviewed, expected: {outcome, panel_key, title, panel_plugin, promql, errors, warnings}}]
dashboard: {milestone, reviewed, expected: {outcome, widgets: [{source_path, outcome, panel_key, promql}]}}
```

Entries may carry extra top-level metadata keys (`provenance`, `live_check`, `dataset`, `notes`);
tests read only `source_path`, `milestone`, `reviewed` and `expected`, and ignore everything else.
A request whose OTel metrics exist in the pinned OTel catalog (`fixtures/otel/catalog.yaml`) but are
missing from the Dash0 dataset snapshot (`fixtures/oracle/dash0_default_metrics.yaml`) stays
`translated` and gets the `dataset` block; only metrics found in neither are `blocked` with
`MISSING_METRIC_MAPPING`.

Widget and dashboard expectations are derived from the request expectations: a widget is
translated only if its type is supported (`timeseries`, `query_value`, `note`) and all its requests
are translated; otherwise it is blocked (`UNSUPPORTED_WIDGET` or the requests' error codes).

## Provenance pipeline (development time only)

```text
scripts/extract_cases.py                 pinned dashboards -> fixtures/cases/<svc>/<id>.yaml   (deterministic)
scripts/build_otel_catalog.py            pinned OTel definitions (fixtures/otel/, NOTICE.md) -> fixtures/otel/catalog.yaml (deterministic)
scripts/render_oracle_prompt.py <svc>/<id>   fixtures/oracle/PROMPT.md template + OTel candidates (catalog.yaml, dataset snapshot) -> fixtures/oracle/agent0/<svc>/<id>/prompt.md
  ask Agent0 (dash0 MCP runTask, dataset default) with prompt.md verbatim
  save the YAML answer verbatim         -> fixtures/oracle/agent0/<svc>/<id>/answer.yaml  (header: date, thread link, any quoting fix)
scripts/build_expected.py <svc>/<id>     case + answer + rules overlay + overrides.yaml -> fixtures/expected/<svc>/<id>/expected.yaml
```

`build_expected.py` adds deterministic project rules on top of Agent0's proposal: requests with no
metrics query, and requests that use **any** Datadog function in a query or formula (`.rollup()`,
`.as_count()`, `.weighted()`, `top()`, `per_second()`, `diff()`, ...), are forced to `blocked`, whatever
Agent0 proposed (plans 02/03/05). `ALLOWED_FUNCTIONS` in the script is empty; a function may only be
added through its own plan task with an exact test. Error codes are derived from the source text, not
Agent0's prose; warnings come from template variables and missing aggregators. Every OTel metric in
a translated request is checked against the dataset snapshot and the catalog: present in the dataset →
nothing to note; only in the catalog → stays `translated` with a `dataset` block and a note (no live check
possible); in neither → `blocked` with `MISSING_METRIC_MAPPING`. Other Agent0 choices
(scaling constants, derived metrics, grain) are flagged in `fixtures/expected/REVIEW.md` for a human
decision. The oracle prompt (`fixtures/oracle/PROMPT.md`) states the same rules, but the overlay is
what enforces them.

Agent0's live checks ran against the Dash0 `default` dataset, where receiver data only exists
2026-11-07 ~14:05–15:21 UTC.

## Review (`overrides.yaml`)

Unreviewed expectations are proposals. A human reviews `fixtures/expected/REVIEW.md`, then records
decisions in `fixtures/expected/<svc>/<id>/overrides.yaml`, keyed by request `source_path`:

```yaml
'widgets[0].definition.requests[0]':
  reviewed: true                         # accept as is
'widgets[3].definition.requests[0]':
  reviewed: true
  expected:                              # correct the outcome / PromQL / codes (merged into expected)
    outcome: blocked
    errors: [UNSUPPORTED_FORMULA]
  notes: ['per_minute() needs a reviewed rate rule; blocked for now']
```

Then re-run `uv run scripts/build_expected.py <svc>/<id>`. Overridden entries get
`provenance: {kind: human, ref: .../overrides.yaml}`. A widget counts as reviewed when all its
requests are; a dashboard when all its widgets are.
