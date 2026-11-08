# Local conversion backend

From the repository root:

```sh
uv sync
uv run python -m backend.server --port 3001
```

Open <http://localhost:3001/>. Select Datadog dashboard/monitor JSON files and click
**Convert**, or leave the selection empty to convert the pinned Postgres demo.
Uses the existing `mappings/datadog` folder. Conversion needs no credentials, Node
server or new dependencies. One stdlib HTTP server serves `preview/` and a
synchronous `POST /api/convert`; request files are removed after conversion.

## Optional AI help

Open a Blocked row and click **Ask AI** to request an Agent0 recommendation for that
item. Only that explicit action sends the failed source item, related diagnostics
and checked-in mappings to Agent0. The draft is displayed, never applied or published.

Set `DASH0_AUTH_TOKEN` in the environment or repository `.env`. The existing default
uv `oracle` group supplies the MCP client; no new dependencies. `DASH0_MCP_URL` (or
`DASH0_API_URL`) and `DASH0_DATASET` optionally select the endpoint and dataset.
Uses the documented [runTask / waitForTask API](https://www.dash0.com/docs/dash0/ai/agent0/overview/use-agent0/delegate-to-agent0).

`POST /api/suggest` accepts `{runId, sourceId, sourcePath}` from the latest completed
conversion. The backend verifies that the item is genuinely blocked. Three calls
total per local backend process; reloading or reconverting does not reset the counter.
Dispatched failures/timeouts count; no automatic retries. At zero, the UI says:
**You have used your 3 AI calls. Contact our sales team at sandy@dash0.com.**
Restarting the local server resets its in-memory counter; this is not persistent
per-account billing. Translated warnings remain hidden; other warnings stay short names.

## API

```json
{"files": [{"name": "dashboard.json", "text": "<original JSON text>"}]}
```

`{"files": []}` runs the pinned Postgres demo. Plain, unique `.json` filenames only;
10 MiB maximum request body. Calls the existing `run_convert` with source `datadog`,
the checked-in mappings and JSON output.

Response: `{report, manifest, exitCode, artifacts, runId, ai}`. Report and manifest are unchanged
compiler output; artifacts maps every relative output filename to its exact text,
including source copies, target dashboards/rules, report and manifest. Compiler
exits 0 and 2 return HTTP 200; invalid inputs return HTTP 400 with `{error}`.

**Download results (.json)** saves the response. Keep the download: the server does
not retain runs. It is a JSON bundle, not a ZIP or CLI run directory; extract its
`artifacts` entries to files before using CLI publishing or the Perses viewer.

## Frontend/backend mismatches

| Frontend concept | Backend behavior / UI treatment |
| --- | --- |
| Three result columns | Outcomes are **Translated, Approximated, Assumed, Best effort, Partial, Blocked**. Every row has its category, plus category counts. Translated is the first column; approximated/assumed/best effort go to Review; blocked goes to Blocked. This grouping does not change compiler publish eligibility. |
| Failed/partial dashboards | Dashboard rows/failures remain hidden at Felix's request. Panel/monitor results are shown; the downloaded report retains dashboard outcomes. `partial` is currently dashboard-only, so normally has no visible rows. |
| Translation/refinement progress | One completed response. The UI says Converting while waiting, then shows results. Simulated stage boxes are mock-only; no streamed progress, automatic refinement or mapping selection is claimed. |
| Publish final migration | No publish endpoint. Real runs skip the fake publish button and offer a download. Nothing is sent to Dash0; publishing stays a separate explicit CLI operation. |
| Values / % difference | Offline compilation has no measurements. Real review drawers explicitly flag numeric comparison unavailable; no fake values or percentages. |
| Query comparison per row | Reports carry source paths, diagnostics and optional source query text, not a direct panel-to-target-query pointer. Drawers show available source evidence and every diagnostic; exact target artifacts are in the download. |
| Warnings / review | Translated rows show no warnings. Other categories show warning/remark short names only, without descriptions or examples; blocked errors retain their message/action. Full diagnostics stay in the download. No persisted review action: viewing the UI does not approve mappings or change outcomes. |
| AI workaround | Blocked items from the latest backend conversion support explicit Agent0 recommendations (3 calls). Drafts do not change compiler results. Saved-report mode cannot request AI help. |
| Book a call | No booking service; exhausted AI quota shows the plain sales contact sandy@dash0.com. |
| Input/mapping settings | JSON uploads or pinned demo; fixed Datadog source and checked-in mappings. No account fetch, archives, mapping editor or alternate output format. |
| Migration success | Actual syntax/schema/API/semantics statuses are shown. Offline API/semantics remain `not_run`; conversion does not prove destination import. |

Saved report viewing: `?report=reports/report.json` (report only; no target artifacts).
Standalone `node preview/serve.mjs` can serve saved reports or explicit mock mode;
default conversion requires this Python backend and never falls back to mock data.

## Checks

```sh
uv run migrator check
uv run ruff check backend
uv run mypy --strict backend
node --test preview/backend.test.cjs
```
