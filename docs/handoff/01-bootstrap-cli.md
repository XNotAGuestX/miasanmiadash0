# 01 — Bootstrap, CLI and report: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `npm run dev -- convert --source datadog --input <file|dir>... --mapping <file> --out <dir>` runs offline. It recognizes Datadog dashboards and monitors, accounts for every widget and monitor, and writes source copies, `report.json` and `manifest.json` with deterministic bytes.

**Architecture:**

- Shared code handles input, writers, report and CLI, and depends only on the `SourceProvider` interface and the shared types in `src/target.ts`.
- The Datadog provider recognizes and unwraps assets.
- Translation is out of scope here: every widget and monitor is reported `blocked` until plans 04 and 06.

**Tech Stack:** TypeScript (strict, ESM, NodeNext), Node ≥ 22, commander, zod, yaml, vitest, tsx.

**Spec:** [00-context.md](00-context.md) §2, §4, §5, §6 and §8.

## Global Constraints

- Deterministic output:
  - JSON is written with recursively sorted keys, 2-space indent and a trailing `\n`.
  - YAML is written with sorted map entries.
  - No timestamps, absolute paths or environment data in any artifact.
- `convert` performs no network I/O.
- Exit codes: `0` (all translated), `2` (partial or blocked items), `1` (an input, argument or mapping-file error).
- File ordering uses plain code-unit comparison (`a < b`), never `localeCompare`.
- `COMPILER_VERSION` = `0.1.0`, and it must equal the `package.json` version.

## Review Focus

1. **A non-empty `--out` directory:** refuse with exit 1, so stale artifacts never mix with new ones. Covered by `convert refuses a non-empty out dir` (Task 6).
2. **Symlinks inside an input folder:** don't follow them, so the walk can't loop or escape the input root. Covered by `skips symlinks` (Task 3).
3. **Two inputs that produce the same source ID:** exit 1, never silently overwrite. Covered by `duplicate source ids throw` (Task 3).
4. **A folder that mixes Datadog assets with other JSON:** skip the other files with an `UNSUPPORTED_ASSET_KIND` warning; they don't change the exit code. Covered by `unknown json is skipped with a warning` (Task 4).
5. **The same inputs run twice:** byte-identical outputs. Covered by `convert is deterministic` (Task 6).

---

### Task 1: Package skeleton

**Files:**
- Create: `package.json`, `package-lock.json` (via npm), `tsconfig.json`, `vitest.config.ts`, `src/version.ts`
- Test: `tests/version.test.ts`

**Interfaces:**
- Produces: `export const COMPILER_VERSION: string` from `src/version.ts`.

- [ ] **Step 1: Create the package.**
  - Run `npm init -y`, then set `"name": "dash0-dashboard-migrator"`, `"version": "0.1.0"`, `"type": "module"`, `"private": true` and `"engines": {"node": ">=22"}`.
  - Scripts: `"dev": "tsx src/cli.ts"`, `"build": "tsc -p tsconfig.json"`, `"typecheck": "tsc -p tsconfig.json --noEmit"`, `"test": "vitest run"`.
  - Install: `npm i commander zod yaml` and `npm i -D typescript tsx vitest @types/node`.
  - `tsconfig.json`: `strict`, `module`/`moduleResolution` `NodeNext`, `target` `ES2023`, `resolveJsonModule`, `outDir: dist`, `rootDir: .`, `include: ["src", "tests"]`.

- [ ] **Step 2: Write the failing test.**

```ts
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { COMPILER_VERSION } from "../src/version.js";

describe("version", () => {
  it("matches package.json", () => {
    const pkg = JSON.parse(readFileSync("package.json", "utf8"));
    expect(COMPILER_VERSION).toBe(pkg.version);
  });
});
```

- [ ] **Step 3: Run it.** Run `npm test`. It must FAIL because the module can't be found.
- [ ] **Step 4: Implement it.** Add `src/version.ts`: `export const COMPILER_VERSION = "0.1.0";`.
- [ ] **Step 5: Verify.** `npm test && npm run typecheck` must both pass.
- [ ] **Step 6: Commit.** `git add package.json package-lock.json tsconfig.json vitest.config.ts src tests && git commit -m "chore: bootstrap TypeScript CLI package"`.

### Task 2: Shared types and stable writers

**Files:**
- Create: `src/target.ts`, `src/write.ts`
- Test: `tests/write.test.ts`

**Interfaces:**
- Produces, in `src/target.ts`. Later plans import these names exactly:

```ts
export type Severity = "error" | "warning" | "info";
export type DiagnosticCode = /* every code in 00-context §8 as a string-literal union */;
export interface Diagnostic { code: DiagnosticCode; severity: Severity; sourceId: string; sourcePath: string; message: string; suggestedAction: string; sourceText?: string }
export type Outcome = "translated" | "partial" | "blocked";
export type ItemKind = "dashboard" | "widget" | "monitor";
export interface ItemResult { sourceId: string; sourcePath: string; kind: ItemKind; title: string; outcome: Outcome }
export interface PersesQuery { kind: "TimeSeriesQuery"; spec: { plugin: { kind: "PrometheusTimeSeriesQuery"; spec: { query: string; seriesNameFormat?: string } } } }
export interface PersesPanel { kind: "Panel"; spec: { display: { name: string; description: string }; plugin: { kind: string; spec: Record<string, unknown> }; queries: PersesQuery[] } }
export interface PersesGridItem { x: number; y: number; width: number; height: number; content: { $ref: string } }
export interface PersesGrid { kind: "Grid"; spec: { display?: { title: string }; items: PersesGridItem[] } }
export interface PersesDashboard { kind: "Dashboard"; metadata: { name: string; project: string }; spec: { display: { name: string; description: string }; duration: string; variables: unknown[]; panels: Record<string, PersesPanel>; layouts: PersesGrid[] } }
export interface PrometheusRule { alert: string; expr: string; labels: Record<string, string>; annotations: Record<string, string> }
export interface PrometheusRuleGroup { groups: { name: string; interval: string; rules: PrometheusRule[] }[] }
export interface Dash0CheckRule { name: string; expression: string; thresholds: { degraded?: number; failed: number }; interval: string; for: string; enabled: boolean; labels: Record<string, string>; annotations: { summary: string; description: string } }
export interface DashboardArtifact { slug: string; sourceId: string; dashboard: PersesDashboard }
export interface RuleArtifact { slug: string; sourceId: string; prometheusRuleGroup: PrometheusRuleGroup; checkRule: Dash0CheckRule }
export interface CompileResult { dashboards: DashboardArtifact[]; rules: RuleArtifact[]; items: ItemResult[]; diagnostics: Diagnostic[] }
export type Level = "passed" | "failed" | "not_run";
export interface ValidationLevels { syntax: Level; schema: Level; api: Level; semantics: Level }
```

- Produces, in `src/write.ts`:
  - `stableStringify(value: unknown): string`
  - `toYaml(value: unknown): string`
  - `slugify(title: string): string`
  - `assignSlugs(titles: string[]): string[]`
  - `sha256(text: string): string` (hex)

- [ ] **Step 1: Write the failing tests.**

```ts
import { describe, expect, it } from "vitest";
import { assignSlugs, sha256, slugify, stableStringify, toYaml } from "../src/write.js";

describe("write", () => {
  it("sorts keys recursively with trailing newline", () => {
    expect(stableStringify({ b: 1, a: { d: [{ z: 1, y: 2 }], c: 2 } }))
      .toBe('{\n  "a": {\n    "c": 2,\n    "d": [\n      {\n        "y": 2,\n        "z": 1\n      }\n    ]\n  },\n  "b": 1\n}\n');
  });
  it("yaml sorts map entries", () => {
    expect(toYaml({ b: 1, a: 2 })).toBe("a: 2\nb: 1\n");
  });
  it("slugifies titles", () => {
    expect(slugify("Postgres - Metrics")).toBe("postgres-metrics");
    expect(slugify("  ##  ")).toBe("dashboard");
    expect(slugify("a".repeat(80))).toHaveLength(64);
  });
  it("disambiguates slug collisions in order", () => {
    expect(assignSlugs(["A b", "a-b", "A B"])).toEqual(["a-b", "a-b-2", "a-b-3"]);
  });
  it("hashes", () => {
    expect(sha256("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});
```

- [ ] **Step 2: Run it.** Run `npx vitest run tests/write.test.ts`. It must FAIL because the module can't be found.
- [ ] **Step 3: Implement it.**
  - `slugify`: lowercase; replace each run of `[^a-z0-9]` with `-`; trim leading and trailing `-`; cut to 64 characters, then trim a trailing `-` again; return `"dashboard"` if the result is empty.
  - `toYaml`: use `yaml`'s `stringify(value, { sortMapEntries: true })`.
  - `sha256`: use `node:crypto`.
- [ ] **Step 4: Verify.** Run the same test. It must PASS.
- [ ] **Step 5: Commit.** `git commit -am "feat: shared target types and deterministic writers"`. Add the new files first.

### Task 3: Collecting input files

**Files:**
- Create: `src/input.ts`
- Test: `tests/input.test.ts`

**Interfaces:**
- Produces:
  - `export interface InputFile { sourceId: string; path: string; text: string; sha256: string }`
  - `export class InputError extends Error {}`
  - `export function collectInputFiles(paths: string[]): InputFile[]`

**Rules:**

- A file argument must end in `.json`; its `sourceId` is the basename.
- A directory argument is walked recursively, collecting only `*.json` files and skipping symlinks (use `lstat`). The `sourceId` is `<basename(dir)>/<posix relative path>`.
- The result is sorted by `sourceId`.
- A missing path throws `InputError("input not found: <path>")`.
- A duplicate `sourceId` throws `InputError("DUPLICATE_SOURCE_ID: <id>")`.

- [ ] **Step 1: Write the failing tests.**
  - Each test builds a temporary tree with `mkdtempSync(join(tmpdir(), "in-"))`.
  - `collects json files recursively and sorted`:
    - Tree: `root/b.json`, `root/a/z.json`, `root/a/readme.md`.
    - Expect `collectInputFiles([root]).map(f => f.sourceId)` to be `["<root-base>/a/z.json", "<root-base>/b.json"]`.
  - `file input uses basename`: expect `collectInputFiles([join(root, "b.json")])[0].sourceId` to be `"b.json"`.
  - `duplicate source ids throw`: pass the same file twice; expect it to throw `/DUPLICATE_SOURCE_ID: b.json/`.
  - `missing path throws`: expect `/input not found/`.
  - `skips symlinks`: add `symlinkSync(root, join(root, "loop"))`; expect the result to contain no `sourceId` with `loop`.
- [ ] **Step 2: Run it.** Run `npx vitest run tests/input.test.ts`. It must FAIL.
- [ ] **Step 3: Implement `collectInputFiles(paths: string[]): InputFile[]` in `src/input.ts`.**
- [ ] **Step 4: Verify.** Run the same tests. They must PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: collect file and folder inputs deterministically"`.

### Task 4: Pinned fixtures and Datadog asset recognition

**Files:**
- Create: `fixtures/datadog/integrations-core/NOTICE.md`, `fixtures/datadog/integrations-core/LICENSE`
- Create: `fixtures/datadog/integrations-core/postgres/dashboards/{postgresql_dashboard.json,postgresql_screenboard_dashboard.json}`
- Create: `fixtures/datadog/integrations-core/postgres/monitors/{percent_usage_connections.json,replication_delay.json}`
- Create: `src/source/datadog/assets.ts`
- Test: `tests/datadog/assets.test.ts`

**Interfaces:**
- Consumes: `InputFile` (Task 3); `Diagnostic` and `ItemResult` (Task 2).
- Produces, in `src/source/provider.ts` (the type only; Task 5 adds the rest):
  - `export interface SourceAsset { sourceId: string; kind: "dashboard" | "monitor"; title: string; raw: unknown; body: Record<string, unknown> }`
- Produces, in `src/source/datadog/assets.ts`:
  - `export function recognizeAssets(files: InputFile[]): { assets: SourceAsset[]; diagnostics: Diagnostic[] }`

**Recognition rules:**

- **Dashboard:** an object with a `widgets` array and a `layout_type` string. `body` is the object itself.
- **Wrapped monitor:** an object whose `definition` is an object with string `query` and string `type`. `body` is the `definition`.
- **Raw monitor:** an object with string `query`, string `type` and an `options` object. `body` is the object itself.
- **Anything else:** a warning `UNSUPPORTED_ASSET_KIND` at `sourcePath: ""`; no asset is produced.
- **Invalid JSON:** throws `InputError("INVALID_JSON: <sourceId>: <parser message>")`.
- `title` is the dashboard's `title`, or the monitor's `name`, or `""`.

- [ ] **Step 1: Download the pinned fixtures.** Run:

```bash
SHA=a9b9e42b7e484861ecbd1f5919da7c52a694b74d; D=fixtures/datadog/integrations-core
mkdir -p $D/postgres/dashboards $D/postgres/monitors
for f in dashboards/postgresql_dashboard.json dashboards/postgresql_screenboard_dashboard.json monitors/percent_usage_connections.json monitors/replication_delay.json; do
  gh api "repos/DataDog/integrations-core/contents/postgres/assets/$f?ref=$SHA" --jq .content | base64 -d > $D/postgres/$f; done
gh api "repos/DataDog/integrations-core/contents/LICENSE?ref=$SHA" --jq .content | base64 -d > $D/LICENSE
```

Write `NOTICE.md` with the repository URL, the SHA, the license (BSD-3-Clause, copied unchanged) and the list of copied files.

- [ ] **Step 2: Write the failing tests.**
  - `recognizes the postgres dashboards and monitors`: on `collectInputFiles(["fixtures/datadog/integrations-core/postgres"])`, expect:
    - kinds `["dashboard", "dashboard", "monitor", "monitor"]`;
    - the first title `"Postgres - Metrics"`;
    - the monitor `body.query` `"avg(last_15m):avg:postgresql.percent_usage_connections{*} > 0.9"`.
  - `unknown json is skipped with a warning`: an `InputFile` with text `{"hello":1}` gives no assets and one diagnostic `{code: "UNSUPPORTED_ASSET_KIND", severity: "warning"}`.
  - `invalid json throws`: text `{` throws `/INVALID_JSON/`.
- [ ] **Step 3: Run it.** Run `npx vitest run tests/datadog/assets.test.ts`. It must FAIL.
- [ ] **Step 4: Implement `recognizeAssets`.**
- [ ] **Step 5: Verify.** The tests must PASS.
- [ ] **Step 6: Commit.** `git add fixtures src tests && git commit -m "feat: recognize Datadog dashboards and monitors; pin postgres fixtures"`.

### Task 5: The provider table and the Datadog provider skeleton

**Files:**
- Create: `src/source/provider.ts` (extending Task 4's type), `src/source/datadog/index.ts`
- Test: `tests/provider.test.ts`

**Interfaces:**
- Produces:

```ts
export interface CompileOptions { project: string }
export interface ProviderLoadResult { assets: SourceAsset[]; diagnostics: Diagnostic[] }
export interface SourceProvider {
  readonly id: string;
  load(files: InputFile[]): ProviderLoadResult;
  compile(assets: SourceAsset[], mapping: unknown, options: CompileOptions): CompileResult;
}
export const providers: Readonly<Record<string, SourceProvider>>; // { datadog: datadogProvider }
export function getProvider(id: string): SourceProvider; // unknown id throws InputError("unknown --source '<id>'; known: datadog")
```

- Skeleton behaviour of `datadogProvider.compile`. Plans 04 and 06 replace it:
  - Each dashboard gives an item `{kind: "dashboard", sourcePath: "", outcome: "blocked"}`.
  - Each top-level widget gives an item `{kind: "widget", sourcePath: "widgets[i]", title: definition.title ?? "", outcome: "blocked"}`, with the error `UNSUPPORTED_WIDGET`: `Widget type '<type>' is not supported yet.`
  - Each monitor gives an item `{kind: "monitor", outcome: "blocked"}`, with the error `UNSUPPORTED_MONITOR_TYPE`: `Monitor conversion is not supported yet.`
  - `dashboards` and `rules` are empty.

- [ ] **Step 1: Write the failing tests.**
  - `getProvider("datadog").id === "datadog"`.
  - `getProvider("grafana")` throws `/unknown --source 'grafana'; known: datadog/`.
  - Compiling the pinned postgres folder gives 2 dashboards + 9 widgets ("Postgres - Metrics") + 10 widgets ("Postgres - Overview", all top-level `group`) + 2 monitors = 23 items, all `blocked`.
- [ ] **Step 2: Run it.** It must FAIL. **Step 3: Implement.** **Step 4: Verify.** It must PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: SourceProvider table with Datadog skeleton provider"`.

### Task 6: Report, manifest, runConvert and the CLI

**Files:**
- Create: `src/report.ts`, `src/convert.ts`, `src/cli.ts`
- Test: `tests/report.test.ts`, `tests/convert.test.ts`, `tests/cli.test.ts`

**Interfaces:**
- Consumes: everything above.
- Produces:

```ts
// src/report.ts
export type Counts = Record<Outcome, number>;
export interface Summary { dashboards: Counts; widgets: Counts; monitors: Counts; skippedFiles: number }
export interface Report { reportVersion: 1; provider: string; compilerVersion: string; format: "json" | "yaml"; mapping: { sourceId: string; sha256: string }; summary: Summary; items: ItemResult[]; diagnostics: Diagnostic[]; validation: ValidationLevels }
export interface ManifestEntry { path: string; kind: "dashboard" | "prometheus-rule" | "check-rule" | "source"; sourceId: string; sha256: string; outcome: Outcome | null /* null for source copies */; eligible: boolean /* true only when outcome === "translated" */ }
export interface Manifest { manifestVersion: 1; provider: string; compilerVersion: string; format: "json" | "yaml"; entries: ManifestEntry[] }
export function summarize(items: ItemResult[], skippedFiles: number): Summary;
export function exitCodeFor(items: ItemResult[]): 0 | 2;
export function formatSummary(report: Report): string;
// src/convert.ts
export interface ConvertOptions { source: string; inputs: string[]; mapping: string; out: string; format: "json" | "yaml"; project: string }
export interface ConvertResult { report: Report; manifest: Manifest; exitCode: 0 | 1 | 2 }
export function runConvert(opts: ConvertOptions): ConvertResult;
```

**Output layout under `--out`:**

- `source/<sourceId>`: exact copies of the input text.
- `dashboards/<slug>.json|yaml`.
- `rules/<slug>.prometheus.json|yaml`.
- `check-rules/<slug>.json` (always JSON; this is the Dash0 API body).
- `report.json` and `manifest.json` (always JSON).

The manifest entries are sorted by `path`.

**`formatSummary`:** one line per dashboard, `<OUTCOME padded to 10><slug> <translated>/<total> widgets`; one line per monitor; then a totals line.

**CLI:** `convert --source <id> --input <path...> --mapping <file> --out <dir> [--format json|yaml] [--project <name>]`.

- Defaults: `--format json` and `--project datadog-migration`.
- `InputError` and a mapping file that won't parse as JSON both print `error: <message>` to stderr and exit 1.
- A non-empty `--out` throws `InputError("output directory is not empty: <out>")`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/report.test.ts`:
    - `exitCodeFor([])` is `0`.
    - Any `blocked` or `partial` item gives `2`.
    - `summarize` counts per kind and outcome.
  - `tests/convert.test.ts`:
    - `convert writes report, manifest and source copies`:
      - Use the pinned postgres folder and the mapping file `{"version":1,"source":"datadog","metrics":{}}` (write it to a temporary directory).
      - Expect: `exitCode` is `2`; `report.summary.dashboards.blocked` is `2`; `out/source/postgres/monitors/replication_delay.json` exists and is byte-equal to the fixture; and `report.validation` is `{syntax:"not_run", schema:"not_run", api:"not_run", semantics:"not_run"}`.
    - `convert refuses a non-empty out dir`: throws `/output directory is not empty/`.
    - `convert is deterministic`: two runs into two fresh directories; every file is byte-equal (compare the sorted relative file lists, then the contents).
  - `tests/cli.test.ts`:
    - Run `spawnSync("node_modules/.bin/tsx", ["src/cli.ts", "convert", "--source", "nope", "--input", "x", "--mapping", "m", "--out", "o"])`.
    - Expect `status` `1` and stderr matching `/unknown --source 'nope'/`.
- [ ] **Step 2: Run them.** They must FAIL.
- [ ] **Step 3: Implement `report.ts`, `convert.ts` and `cli.ts`.**
  - `runConvert` order: `getProvider` → `collectInputFiles` → read and `JSON.parse` the mapping → `provider.load` → `provider.compile` → write artifacts → write the report and manifest → return.
- [ ] **Step 4: Verify.** `npm test && npm run typecheck` must pass.
- [ ] **Step 5: Smoke test.** Run `npm run dev -- convert --source datadog --input fixtures/datadog/integrations-core/postgres --mapping <tmp>/empty-mapping.json --out /tmp/conv1; echo $?`. Expect the summary lines and exit code `2`.
- [ ] **Step 6: Document.** Add "Install / test / convert" commands, exactly as they were run, to `README.md`. Mark plan 01 Done in `docs/handoff/README.md`.
- [ ] **Step 7: Commit.** `git commit -m "feat: convert command with report, manifest and exit codes"`.
