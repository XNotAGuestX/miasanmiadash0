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
    """One line per dashboard and monitor, then a totals line."""
    lines: list[str] = []
    items = report["items"]
    for item in items:
        if item["kind"] == "dashboard":
            widgets = [
                w for w in items if w["kind"] == "widget" and w["sourceId"] == item["sourceId"]
            ]
            done = sum(1 for w in widgets if w["outcome"] == "translated")
            name = slugs.get(item["sourceId"], item["sourceId"])
            lines.append(f"{item['outcome'].upper():<10} {name} {done}/{len(widgets)} widgets")
        elif item["kind"] == "monitor":
            lines.append(f"{item['outcome'].upper():<10} {item['sourceId']} monitor")
    s = report["summary"]
    lines.append(
        "total: dashboards {d}, widgets {w}, monitors {m}, skipped files {k}".format(
            d=_fmt(s["dashboards"]),
            w=_fmt(s["widgets"]),
            m=_fmt(s["monitors"]),
            k=s["skippedFiles"],
        )
    )
    return "\n".join(lines)


def _fmt(counts: dict[str, int]) -> str:
    return "/".join(f"{counts[o]} {o}" for o in OUTCOMES)
