# 02 — Datadog metric query parser: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure, total parser that turns one Datadog metric query string into a typed `MetricQuery`, or a precise error with an offset. It consumes the entire input.

**Architecture:** A hand-written scanner with one character index, over the bounded grammar below. There are no regex replacements and no partial acceptance. Functions such as `.rollup()` are parsed so later stages can reject them precisely. Anything outside the grammar is an error.

**Tech Stack:** Python 3.13 (uv), pytest.

**Spec:** [00-context.md](00-context.md) §2 (rule 3) and §6.

**Depends on:** plan 01, for `Diagnostic` codes only.

## Global Constraints

- `parseMetricQuery` is pure: it never throws on any string input; it always returns a `ParseResult`.
- The error offset is a 0-based UTF-16 index into the original string.
- The grammar is fixed by this plan. Widening it needs a new test first.

## Grammar

```text
query       := [aggregator ":"] metric "{" filterList "}" [" by {" tagList "}"] function*
aggregator  := "avg" | "sum" | "min" | "max"
metric      := ident ("." ident)*
ident       := [A-Za-z_][A-Za-z0-9_]*
filterList  := "*" | filter ("," " "? filter)*
filter      := "$" ident                      -- template variable
             | tagKey ":" tagValue
tagKey      := [A-Za-z][A-Za-z0-9_./-]*
tagValue    := [A-Za-z0-9_./:@-]+             -- '*', '!', quotes and whitespace are NOT allowed
tagList     := tagKey ("," " "? tagKey)*
function    := "." ident "(" [arg ("," " "? arg)*] ")"
arg         := [A-Za-z0-9_.'-]+
```

**Rejection rules:**

- A leading `ident "("` (for example `top(`, `anomalies(`, `per_second(`) gives `UNSUPPORTED_QUERY_FUNCTION` with the function name.
- Any other deviation gives `UNSUPPORTED_QUERY_SYNTAX` at the first offending offset. That includes negation `!`, the boolean words `OR`, `AND`, `IN` and `NOT`, wildcard values, quotes, arithmetic and trailing input.

## Review Focus

1. **`OR` or `AND` inside braces, written with spaces** (`{env:a OR env:b}`): reject it, never accept `env:a`. Covered by `rejects boolean filters` (Task 1).
2. **A wildcard value** (`{host:db-*}`): reject it, because exact-match filters are the only supported kind. Covered by `rejects wildcard values` (Task 1).
3. **Trailing junk after a valid query** (`avg:x{*} / 2`): reject it with the offset of `/`. Covered by `rejects trailing input` (Task 1).
4. **Empty or whitespace-only input:** a syntax error at offset 0, not a crash. Covered by `rejects empty input` (Task 1).
5. **Every real query in the pinned Postgres "Metrics" dashboard:** they all parse. Covered by `parses every golden dashboard query` (Task 2).

---

### Task 1: Model and parser

**Files:**
- Create: `src/migrator/source/datadog/model.py`, `src/migrator/source/datadog/parse_query.py`
- Test: `tests/datadog/test_parse_query.py`

**Interfaces:**
- Produces:

```ts
// model.py
export type SpaceAggregator = "avg" | "sum" | "min" | "max";
export type TagFilter = { kind: "tag"; key: string; value: string } | { kind: "variable"; name: string };
export interface QueryFunction { name: string; args: string[] }
export interface MetricQuery { aggregator: SpaceAggregator | null; metric: string; filters: TagFilter[]; groupBy: string[]; functions: QueryFunction[] }
export type ParseResult =
  | { ok: true; query: MetricQuery }
  | { ok: false; code: "UNSUPPORTED_QUERY_SYNTAX" | "UNSUPPORTED_QUERY_FUNCTION"; offset: number; message: string };
// parse_query.py
export function parseMetricQuery(text: string): ParseResult;
```

- [ ] **Step 1: Write the failing tests.**

```ts
import { describe, expect, it } from "vitest";
import { parseMetricQuery as p } from "../../src/source/datadog/parse-query.js";

describe("parseMetricQuery", () => {
  it("parses aggregator, variable filter and group by", () => {
    expect(p("avg:postgresql.connections{$scope} by {db}")).toEqual({ ok: true, query: {
      aggregator: "avg", metric: "postgresql.connections",
      filters: [{ kind: "variable", name: "scope" }], groupBy: ["db"], functions: [] } });
  });
  it("parses a missing aggregator as null", () => {
    expect(p("postgresql.rows_inserted{$scope}")).toMatchObject({ ok: true, query: { aggregator: null } });
  });
  it("parses star and tag filters", () => {
    expect(p("avg:x.y{*}")).toMatchObject({ ok: true, query: { filters: [] } });
    expect(p("max:system.cpu.iowait{env:demo, host:db-1}")).toMatchObject({ ok: true, query: {
      filters: [{ kind: "tag", key: "env", value: "demo" }, { kind: "tag", key: "host", value: "db-1" }] } });
  });
  it("parses trailing functions for later rejection", () => {
    expect(p("sum:x{*}.rollup(max, 60).as_count()")).toMatchObject({ ok: true, query: {
      functions: [{ name: "rollup", args: ["max", "60"] }, { name: "as_count", args: [] }] } });
  });
  it("rejects wrapping functions", () => {
    expect(p("anomalies(avg:x{*}, 'basic', 2)")).toEqual({ ok: false, code: "UNSUPPORTED_QUERY_FUNCTION", offset: 0, message: "Function 'anomalies' is not supported." });
  });
  it("rejects negation", () => {
    expect(p("avg:x{!env:prod}")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 6 });
  });
  it("rejects boolean filters", () => {
    expect(p("avg:x{env:a OR env:b}")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 11 });
  });
  it("rejects wildcard values", () => {
    expect(p("avg:x{host:db-*}")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 14 });
  });
  it("rejects trailing input", () => {
    expect(p("avg:x{*} / 2")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 8 });
  });
  it("rejects empty input", () => {
    expect(p("")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 0 });
    expect(p("   ")).toMatchObject({ ok: false, code: "UNSUPPORTED_QUERY_SYNTAX", offset: 0 });
  });
});
```

- [ ] **Step 2: Run it.** Run `uv run migrator test tests/datadog/test_parse_query.py`. It must FAIL because the module can't be found.
- [ ] **Step 3: Implement `parseMetricQuery`** as a recursive-descent scanner over the grammar above.
  - Error messages:
    - syntax: `Unexpected '<char>' at offset <n>.`, or `Unexpected end of query at offset <n>.`;
    - function: `Function '<name>' is not supported.`
  - The leading-function check: if the input matches `^[A-Za-z_][A-Za-z0-9_]*\(`, return `UNSUPPORTED_QUERY_FUNCTION` at offset 0.
- [ ] **Step 4: Verify.** Run the same tests. They must PASS.
- [ ] **Step 5: Commit.** `git add src/source/datadog tests/datadog && git commit -m "feat: bounded Datadog metric query parser"`.

### Task 2: Golden corpus check

**Files:**
- Test: `tests/datadog/test_parse_query_golden.py`

**Interfaces:**
- Consumes: `parseMetricQuery`, and the pinned fixture from plan 01.

- [ ] **Step 1: Write the test `parses every golden dashboard query`.**
  - Load `fixtures/datadog/integrations-core/postgres/dashboards/postgresql_dashboard.json`.
  - Collect every `widgets[*].definition.requests[*].queries[*].query`; there are 23 strings (4+1+3+1+3+6+1+2+2).
  - Assert that every result has `ok === true`.
  - Assert the `groupBy` of widget 1 equals `["db"]`.
- [ ] **Step 2: Write `screenboard queries: count of parse failures is stable`.**
  - Walk "Postgres - Overview" recursively, including group children, and collect every `queries[*].query` whose `data_source` is `metrics`.
  - Assert the exact number of `ok:false` results, and the list of failing `code`s.
  - First run it once, record the observed numbers in the test, and review them by hand. That turns the corpus into a regression baseline for later grammar changes.
- [ ] **Step 3: Verify.** Run `uv run migrator test tests/datadog`. It must PASS.
- [ ] **Step 4: Commit.** `git commit -am "test: golden query corpus for the parser"`.
