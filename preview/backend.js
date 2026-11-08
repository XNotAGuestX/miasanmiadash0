// The one place the UI talks to the backend. app.js calls only these two functions:
//
//   await MigrateBackend.load()       -> array of UI items (see INTEGRATION.md for the shape)
//   await MigrateBackend.process(it)  -> resolves when that item is finished; it.status must be set by then
//
// Two sources:
//   - mock (default): window.MIGRATION_ITEMS from data.js, with a simulated delay per item.
//   - report: open the page with ?report=<url> to show a real `migrator convert` report.json.
//     The URL must be same-origin (for example reports/report.json, or a local API route).
//
// No conversion happens here. The UI only displays what the deterministic converter decided.
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const reportUrl = params.get("report");

  // report.json outcome -> UI column. Kept in step with migrator.report.CONVERTED.
  const STATUS = {
    translated: "converted",
    approximated: "converted",
    assumed: "converted",
    best_effort: "converted",
    partial: "review",
    blocked: "unsupported",
  };
  const SEVERITY_RANK = { error: 0, warning: 1, info: 2 };

  // Is diagnostic path `p` at or below item path `base`? (Same rule as migrator.report.)
  const within = (p, base) => base === "" || p === base || p.startsWith(base + ".") || p.startsWith(base + "[");

  function fromReport(report) {
    if (!report || !Array.isArray(report.items)) throw new Error("report.json has no items array");
    const diags = Array.isArray(report.diagnostics) ? report.diagnostics : [];
    const dashTitle = new Map(
      report.items.filter((i) => i.kind === "dashboard").map((i) => [i.sourceId, i.title]));

    // One UI item per widget and per monitor: the units a person checks. Dashboards are their sum.
    return report.items
      .filter((i) => i.kind === "widget" || i.kind === "monitor")
      .map((i, n) => {
        const status = STATUS[i.outcome];
        if (!status) throw new Error(`unknown outcome "${i.outcome}" in report.json`);
        const mine = diags
          .filter((d) => d.sourceId === i.sourceId && within(d.sourcePath || "", i.sourcePath || ""))
          .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 3) - (SEVERITY_RANK[b.severity] ?? 3));
        const top = mine.find((d) => d.severity !== "info");
        const remarks = (i.remarks || []).join(", ");
        const why = top ? top.message
          : status === "converted"
            ? (remarks ? `Converted with remarks: ${remarks}.` : "Converted.")
            : "No diagnostic recorded.";
        return {
          id: `r${n}`,
          name: i.title || i.sourcePath || i.sourceId,
          status,
          outcome: i.outcome,
          why,
          action: top && top.suggestedAction ? top.suggestedAction : "",
          from: top && top.sourceText ? top.sourceText : `${i.sourceId} ${i.sourcePath}`.trim(),
          to: status === "unsupported" ? (top ? top.code : "blocked") : (dashTitle.get(i.sourceId) || i.kind),
          source: { id: i.sourceId, path: i.sourcePath, kind: i.kind },
          // No `suggestion`: the backend never proposes fixes (AGENTS.md: no model in the conversion path).
        };
      });
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  window.MigrateBackend = {
    mode: reportUrl ? "report" : "mock",

    async load() {
      if (!reportUrl) return window.MIGRATION_ITEMS;
      const res = await fetch(reportUrl, { cache: "no-store" });
      if (!res.ok) throw new Error(`Could not load ${reportUrl} (HTTP ${res.status})`);
      return fromReport(await res.json());
    },

    // Mock: pretend each item takes a moment. Report: the result is already known, so just
    // pace the dial. A live backend would await the item's real result here.
    async process(it) {
      await sleep(reportUrl ? 60 + Math.random() * 120 : 700 + Math.random() * 1000);
      return it;
    },

    fromReport, // exposed for tests and the console
  };
})();
