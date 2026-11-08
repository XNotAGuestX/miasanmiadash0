# Alert and function extension comparison

Issue [#165](https://github.com/XNotAGuestX/thinchackdash/issues/165) adds a bounded
eight-case suite for the deterministic query/alert extensions. The source assets are
synthetic Datadog inputs. The normal offline compiler produces every destination artifact;
the live harness binds run filters and evaluates the original source functions/formula.
No model participates in conversion or verification.

The suite uses the retained infrastructure stream from
[#157](https://github.com/XNotAGuestX/thinchackdash/issues/157), with ten one-minute
buckets, five minutes of prior monitor/rate history, and two minutes ingestion allowance.
The Redis used/RSS formula is sent to Datadog as separate parsed metric leaves and a
formula. Its five-minute `avg`/`max` reduction is computed on the aligned source buckets,
then compared with the numeric left side of the generated disabled check rule. This
follows Datadog's documented
[classic arithmetic evaluation order](https://docs.datadoghq.com/monitors/guide/as-count-in-monitor-evaluations/).
`as_count()` monitor expressions remain blocked by the compiler because their evaluation
order differs. The harness never approximates an unrecognized monitor expression.

The tolerances are declared in `scripts/live/suites/extensions.yaml` before the live
comparison: **4.9%** for weighted gauges, rollups and explicit rates; **3%** for the
baseline gauge, exact dashboard ratio, and arithmetic monitors. Absolute tolerance is
zero. Every configured series requires full finite bucket coverage and nonzero data.
Threshold decisions must match at every bucket with zero numeric tolerance, independently
of the value comparison. Failures stay in the evidence and do not widen these tolerances.

```sh
uv run scripts/live_compare.py \
  --dataset-config scripts/live/datasets/infrastructure.yaml \
  --tests scripts/live/suites/extensions.yaml \
  --datadog-semantic-mode combined \
  --dash0-dataset default \
  --stream-dir /private/tmp/thinchackdash-157/out/live/infrastructure-stream \
  --env-file /Users/felix/tum/artemis/thinchackdash/.env \
  --out out/live/extensions
```

Use a new output directory after changing compiler artifacts or inputs; reuse the same
directory to preserve fixed windows and import receipts. `--dry-run` performs no vendor
requests. Checks remain disabled. Remote assets and the retained stream stay available;
their cleanup is a separate explicitly requested action.

The harness uses the official
[Datadog timeseries API](https://docs.datadoghq.com/api/latest/metrics/query-timeseries-data-across-multiple-products/)
to evaluate source formulas. It does not create or execute a Datadog monitor. Numeric
agreement does not verify alert scheduling, no-data handling, notifications, interpolation
across arbitrary gaps or weighted ephemeral-series churn. Steady shared telemetry can
support an empirical approximation result without proving those broader semantics.
The two monitor fixtures do not configure `evaluation_delay`; delayed evaluation is not
covered by this suite.

Six focused tests cover category/tolerance declaration, complete arithmetic leaf binding,
Combined mode on every leaf, trailing-syntax rejection, source threshold checks and
conflicting-host rejection. The broader harness retains its strict data/coverage checks.

Live source preflight observed one series with ten finite buckets for each of weighted
Redis memory, average/max rollup Redis memory and PostgreSQL explicit rate. This establishes
source availability only; the integrated destination comparison is recorded separately.
