"""report.json, manifest.json and the terminal summary."""

from __future__ import annotations

from typing import Any, Literal

from migrator.target import ItemResult, Outcome

OUTCOMES: tuple[Outcome, ...] = ("translated", "partial", "blocked")
ManifestKind = Literal["dashboard", "prometheus-rule", "check-rule", "source"]


def _counts() -> dict[str, int]:
    return {o: 0 for o in OUTCOMES}


def summarize(items: list[ItemResult], skipped_files: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "dashboards": _counts(),
        "widgets": _counts(),
        "monitors": _counts(),
        "skippedFiles": skipped_files,
    }
    for item in items:
        summary[f"{item.kind}s"][item.outcome] += 1
    return summary


def exit_code_for(items: list[ItemResult]) -> Literal[0, 2]:
    return 2 if any(i.outcome != "translated" for i in items) else 0


def manifest_entry(
    path: str, kind: ManifestKind, source_id: str, digest: str, outcome: Outcome | None
) -> dict[str, Any]:
    return {
        "path": path,
        "kind": kind,
        "sourceId": source_id,
        "sha256": digest,
        "outcome": outcome,
        "eligible": outcome == "translated",
    }


def format_summary(report: dict[str, Any], slugs: dict[str, str]) -> str:
    """Dashboards and monitors grouped and aligned, then a totals table."""
    items = report["items"]
    dashboards: list[tuple[str, str, str]] = []
    monitors: list[tuple[str, str, str]] = []
    for item in items:
        outcome = item["outcome"].upper()
        if item["kind"] == "dashboard":
            widgets = [
                w for w in items if w["kind"] == "widget" and w["sourceId"] == item["sourceId"]
            ]
            done = sum(1 for w in widgets if w["outcome"] == "translated")
            name = slugs.get(item["sourceId"], item["sourceId"])
            dashboards.append((outcome, name, f"{done}/{len(widgets)} widgets"))
        elif item["kind"] == "monitor":
            monitors.append((outcome, item["sourceId"], ""))

    lines: list[str] = []
    for title, section in (("Dashboards", dashboards), ("Monitors", monitors)):
        if not section:
            continue
        name_w = max(len(name) for _, name, _ in section)
        lines.append(title)
        for outcome, name, detail in section:
            lines.append(f"  {outcome:<10}  {name:<{name_w}}  {detail}".rstrip())
        lines.append("")

    s = report["summary"]
    header = "".join(f"{o:>12}" for o in OUTCOMES)
    lines.append(f"{'Totals':<12}{header}")
    for kind in ("dashboards", "widgets", "monitors"):
        lines.append(f"  {kind:<10}" + "".join(f"{s[kind][o]:>12}" for o in OUTCOMES))
    lines.append(f"  skipped files: {s['skippedFiles']}")
    return "\n".join(lines)
