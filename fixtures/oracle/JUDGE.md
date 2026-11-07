# Judge prompt (fixed template, issue #87 verifier `judge`)

Development-time only. `scripts/render_judge_prompt.py` fills this template for one dashboard and
`scripts/run_oracle.py --mode judge` sends it to Dash0's agent. The answer is stored verbatim under
`fixtures/oracle/verify/<service>/<dashboard_id>/judge.answer.yaml` and normalized into `judge.yaml`
(`scripts/verify_common.py`). Verdicts are triage signals for the human reviewer, never approval, and
never part of the conversion path (`AGENTS.md`).

The template judges every request of `fixtures/expected/<key>/expected.yaml`, blocked ones included.
It is written to limit agreement bias:

- The expectation under review is shown as an anonymous "candidate", described as an unreviewed draft.
  The prompt never says where it came from (no tool, agent, model or provenance names).
- Each request lists the Datadog side first. The judge must write its own `independent` result from
  the Datadog side alone, before it compares, and `independent` comes before `verdict` in the output.
- The judge must run the candidate PromQL against the dataset and report the series count.
- Verdicts are tied to explicit per-aspect `checks`, and `nit`/`block` need reasons.
- The hard rules are copied verbatim from `PROMPT.md`, so the judge applies the same project rules.

Fill `{…}` placeholders exactly; do not reword the template between runs.

---

Read-only task, do not create or change anything. Answer with one YAML code block only.

You are reviewing expected test outcomes for migrating a Datadog dashboard to a Perses dashboard backed by OpenTelemetry metrics, checked against this Dash0 organization (dataset `{dataset}`). For each Datadog request below there is a candidate outcome: either PromQL (`translated`) or `blocked` with error codes. The candidates are an unreviewed draft. Some may be wrong. Do not assume a candidate is correct, and do not let it shape your own answer.

Which metric to use:
- First choice: a metric that exists in this dataset (verify with the metric catalog and PromQL).
- If no metric in this dataset measures the same thing, use a metric that OpenTelemetry defines, from the OTel metric list at the end of this prompt (collector-contrib receivers and scrapers, semantic conventions, OTel Java JMX scraper). Such a request is still `translated`; it just cannot be live-checked.
- Block with "no OTel metric" only if neither this dataset nor the OTel metric list has a metric that measures the same quantity.
- Equivalence must come from the metric definitions (what is measured, unit, instrument type), never from similar names alone. Use the attribute keys given for a listed metric (dots become `_` in labels).

Dash0 PromQL conventions:
- Select a metric as `{otel_metric_name="<dotted.name>", otel_metric_type="<sum|gauge|histogram>"}`, with further matchers appended as `, <label>="<value>"`.
- Attribute keys become labels with dots replaced by `_`.
- Use `rate(<selector>[$__rate_interval])` for monotonic sums.
- Template variables with a tag prefix and default `*` (e.g. `$host` on tag `host`) become a matcher `<dash0 label>=~"$<name>"`. Template variables without a prefix (e.g. `$scope`) and default `*` are dropped (all series).

Hard rules. The converter is deterministic; anything these rules do not allow is blocked:
- Any Datadog function blocks the whole request, with reason "unsupported function: <name>". That includes trailing functions (`.rollup()`, `.as_count()`, `.as_rate()`, `.weighted()`, `.fill()`) and wrapping functions (`top()`, `per_second()`, `per_minute()`, `diff()`, `timeshift()`, `week_before()`, `abs()`, `default_zero()`, `count_nonzero()`, `anomalies()`, …), in queries or in formulas. Do not approximate a function with `increase`, `topk`, `*_over_time` or `offset`, and do not drop it. Put the closest PromQL you would have used in `notes` only.
- No numeric constants that are not in the Datadog source. If the units differ (percent vs ratio, ns vs s), say so in `notes` and propose a scale with a documentation link; do not apply it in `promql`.
- Use only `$__rate_interval` as a range. Never `$__interval`, `$__range`, subqueries or fixed windows such as `[15m]`.
- Use `rate()` only on monotonic sums, never on gauges.
- If the Datadog metric has no direct OTel equivalent and would have to be computed from other metrics (e.g. dropped = accepted − handled), block the request and put the proposed expression in `notes`.
- If the Datadog series grain differs from the OTel one (per-CPU vs per-host, series duplicated by restarts), say so in `notes`, naming the label that would collapse it.

Rules: a request is all-or-nothing; if any formula cannot be expressed exactly, the whole request is blocked. Never drop a series. Never invent a metric. A request with empty `formulas` displays its single query directly. A request with empty `queries` is not a metrics request (e.g. logs) and is blocked.

Error codes of blocked candidates:
- UNSUPPORTED_DATA_SOURCE: no metrics query (logs, events, other data sources).
- UNSUPPORTED_FORMULA: a function in a formula.
- UNSUPPORTED_QUERY_FUNCTION: a Datadog function in a query.
- MISSING_METRIC_MAPPING: no OTel metric measures the same quantity, or it would have to be derived from other metrics.

How to review each request, in this order:
1. Read only the `datadog` side. Write your own result in `independent`: the list of PromQL strings you would expect (one per displayed formula, in formula order), or `blocked: <reason>` under the hard rules above. Decide this before you look at the candidate, and do not change it afterwards.
2. Compare the candidate with your independent result and with the Datadog side: the measured quantity (same metric definition), unit, aggregation (avg/sum/min/max, rate vs raw value), grouping (`by` labels vs Datadog `by {…}` tags and template variables), and the outcome (translated vs blocked, and the block reason).
3. Run every candidate PromQL against dataset `{dataset}` over 2026-11-07 14:00–15:25 UTC (receiver data only exists in that window) and report the number of series it returns in `live_check`. Where it helps, run your independent PromQL too and compare the series counts. For a metric that is not in the dataset (see the OTel metric list at the end), write `not in dataset`; for a blocked candidate, write `n/a (blocked)`.
4. Set each check to `ok`, `differs` or `n/a`, then the verdict.

Verdicts:
- pass: the candidate has the same quantity, unit, aggregation, grouping and series as the Datadog request; or the candidate is blocked for a correct reason.
- nit: the candidate gives the same numbers apart from a documented unit scale, a grain caveat, or a cosmetic difference (label order, matcher style, redundant parentheses).
- block: a different quantity, aggregation, grouping or series count; or a wrong outcome (translated although the rules require blocking, or blocked although an exact translation exists, or blocked with the wrong code).

For every request below, answer with one YAML list item, in the given order:
- source_path: <as given>
  independent: [<your PromQL strings>]   # or a string "blocked: <reason>"
  verdict: pass | nit | block
  checks: {quantity: ok|differs|n/a, unit: ok|differs|n/a, aggregation: ok|differs|n/a, grouping: ok|differs|n/a, series_count: ok|differs|n/a, outcome: ok|differs}
  live_check: <series count of the candidate PromQL in the window, e.g. "3 series"; "not in dataset"; "n/a (blocked)">
  reasons: [<one short reason per differing check>]   # required for nit and block; [] for pass
  notes: <optional caveats, e.g. the closest PromQL for a blocked request>

Answer for every request exactly once. Quote every YAML string value that contains a colon.

Dashboard: `{title}` (`{fixture}`), template variables: {template_variables}.

Requests ({request_count}):
{requests_block}

OTel metric list (pinned definitions; "in dataset" from a snapshot of dataset `{dataset}`):
{otel_candidates}
