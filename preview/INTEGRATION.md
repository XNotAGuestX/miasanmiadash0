# Connecting the demo UI to the migrator

`preview/` is a static, dependency-free demo page: start, a progress dial, results in three columns, and a page for unsupported items. It never converts anything. It only displays what `migrator convert` decided, so the deterministic, LLM-free rule in AGENTS.md is untouched.

All backend contact goes through one file, [`backend.js`](backend.js). `app.js` calls just two functions:

| Call | Returns | Today |
| --- | --- | --- |
| `await MigrateBackend.load()` | the array of UI items (shape below) | mock: `window.MIGRATION_ITEMS` from `data.js`; report: maps `report.json` |
| `await MigrateBackend.process(item)` | resolves when that item is finished (`item.status` set) | a short delay that paces the dial |

If `load()` throws, its message is shown on the start screen.

## Run it

```bash
node preview/serve.mjs            # http://localhost:3001  (mock data)
# or: python3 -m http.server 3001 --directory preview
```

### Show a real run

```bash
uv run migrator convert --source datadog --input fixtures/... --mapping mappings/datadog --out out/run
cp out/run/report.json preview/reports/report.json      # preview/reports/ is git-ignored
open "http://localhost:3001/?report=reports/report.json"
```

`?report=` takes any same-origin URL, so a local API route works unchanged, for example `?report=/api/report`.

## How a report becomes UI items

There is one UI item per `widget` and per `monitor` in `report.items`. Dashboards are the sum of their widgets.

| `item.outcome` | UI column (`status`) |
| --- | --- |
| `translated`, `approximated`, `assumed`, `best_effort` (= `migrator.report.CONVERTED`) | `converted` |
| `partial` | `review` |
| `blocked` | `unsupported` |

An unknown outcome makes `load()` throw rather than guess.

The other fields come from the report:

- `why` is the item's most severe non-info diagnostic (same `sourceId`, a `sourcePath` at or below the item's). Converted items show their remark tags.
- `action` is that diagnostic's `suggestedAction`.
- `to` is the diagnostic `code` on the unsupported page.

UI item shape:

```js
{ id, name, status: "converted" | "review" | "unsupported",
  why, action?, from?, to?, outcome?, source?: { id, path, kind },
  suggestion?: { code, note } }   // mock only
```

## AI suggestions

`suggestion` exists only in the mock data. It drives the simulated "Ask AI" and "Try with AI" demo paths. The report adapter never sets it, so with a real report those buttons and the AI option card are hidden. Under AGENTS.md, no model may take part in conversion, including optional fallbacks, so don't connect them to a model without an explicit project decision.

## Going live (not built)

To stream progress from a real run instead of loading a finished report:

1. Add a small local endpoint that runs `migrator convert` and returns `report.json`.
2. Point `?report=` at it, or change `load()` to POST the inputs.
3. If you want per-item progress, have the endpoint stream items and make `process(item)` await each one.

Nothing else in `app.js` needs to change. Publishing to Dash0 stays a separate, explicit `migrator publish` step.
