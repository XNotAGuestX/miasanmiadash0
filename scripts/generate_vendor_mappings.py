"""Generate draft mapping entries from Datadog's pinned OpenTelemetry mapping table (#175).

Development-time only; deterministic and LLM-free. The converter reads the output like any
other mapping file. Every entry is `reviewed: null` until a human reviews it.

Inputs (all pinned in the repo):
  fixtures/datadog/otel-mapping.yaml             vendor name pairs, filter, transform
  fixtures/otel/catalog.yaml                     OTel type, monotonicity, unit
  fixtures/datadog/integrations-core/*/metadata.csv   Datadog type, unit, per-unit

An entry is written only when every fact is known and consistent; otherwise the metric is
skipped and keeps blocking as MISSING_METRIC_MAPPING:
- one distinct (otel, filter, transform) for the Datadog name; no attribute-rename transform
- the OTel metric is in the catalog and is a gauge or a sum (no histogram)
- the Datadog type is known; its kind (rule of tests/datadog/test_metric_types.py:
  rate/count or per-second gauge -> rate, other gauge -> gauge) fits the OTel type:
  gauge kind <- OTel gauge or non-monotonic sum; rate kind <- OTel monotonic sum
- the Datadog name is not already mapped or listed as a gap in another mapping file
- the catalog has no conflicts and the units have an explicit, compatible scale rule

Filters become matchers (attribute dots -> underscores, as Dash0 exposes attributes in PromQL
and as the existing mapping files do). A `× N` transform must agree with UNIT_SCALES;
when the table omits it, that explicit unit rule supplies the scale. Unknown or incompatible
units are skipped. Labels: `host -> host_name`, the convention of existing host mappings.

Usage:
  uv run scripts/generate_vendor_mappings.py          # write mappings/datadog/vendor-table.json
  uv run scripts/generate_vendor_mappings.py --check  # exit 1 if the file is stale
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "fixtures" / "datadog" / "otel-mapping.yaml"
CATALOG = ROOT / "fixtures" / "otel" / "catalog.yaml"
METADATA = ROOT / "fixtures" / "datadog" / "integrations-core"
MAPPINGS = ROOT / "mappings" / "datadog"
OUT = MAPPINGS / "vendor-table.json"
LABELS = {"host": "host_name"}
_LABEL = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_SCALE = re.compile(r"× (\S+)")

# Target sample -> Datadog value, after rate() for monotonic sums. Physical factors use
# the pinned metadata's units (SI nano/micro/milli, IEC mebi); named count pairs come
# from the vendor rows and the pinned receiver definitions. A bare OTel "1" is a count
# only for these explicit source units, never for byte/time/CPU quantities.
# No fallback for empty units, unfamiliar spellings or incompatible dimensions.
UNIT_SCALES: dict[tuple[str, str], float] = {
    ("byte", "By"): 1.0,
    ("byte", "{bytes}"): 1.0,
    ("mebibyte", "By"): 1.0 / 1024**2,
    ("core", "{cpu}"): 1.0,
    ("nanocore", "{cpu}"): 1e9,
    ("second", "s"): 1.0,
    ("second", "{seconds}"): 1.0,
    ("second", "{ms}"): 0.001,
    ("millisecond", "ms"): 1.0,
    ("millisecond", "s"): 1000.0,
    ("microsecond", "us"): 1.0,
    ("percent", "%"): 1.0,
    ("fraction", "%"): 0.01,
    ("fraction", "1"): 1.0,
    ("block", "{blks_read}"): 1.0,
    ("buffer", "{buffers}"): 1.0,
    ("connection", "{connections}"): 1.0,
    ("fault", "{faults}"): 1.0,
    ("file", "{files}"): 1.0,
    ("hit", "{blks_hit}"): 1.0,
    ("lock", "{deadlock}"): 1.0,
    ("message", "{messages}"): 1.0,
    ("process", "{processes}"): 1.0,
    ("read", "{operations}"): 1.0,
    ("record", "{ record }"): 1.0,
    ("request", "{request}"): 1.0,
    ("request", "{requests}"): 1.0,
    ("stage", "{ stage }"): 1.0,
    ("table", "{table}"): 1.0,
    ("task", "{ task }"): 1.0,
    ("thread", "{workers}"): 1.0,
    ("write", "{operations}"): 1.0,
}
for _count_unit in (
    "block", "connection", "error", "file", "hit", "miss", "operation", "page",
    "query", "read", "row", "table", "thread", "wait", "write",
):
    UNIT_SCALES[(_count_unit, "1")] = 1.0


def datadog_types() -> dict[str, dict[str, str]]:
    types: dict[str, dict[str, str]] = {}
    for path in sorted(METADATA.glob("*/metadata.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["source"] = f"{path.parent.name}/metadata.csv"
                types.setdefault(row["metric_name"], row)
    return types


def expected_kind(row: dict[str, str]) -> str | None:
    if row["metric_type"] in ("rate", "count"):
        return "rate"
    if row["metric_type"] == "gauge":
        return "rate" if row.get("per_unit_name") == "second" else "gauge"
    return None


def existing_names(directory: Path, skip: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        if path != skip:
            doc = json.loads(path.read_text(encoding="utf-8"))
            names |= set(doc["metrics"]) | set(doc.get("gaps", {}))
    return names


def build(
    rows: list[dict[str, Any]],
    catalog: dict[str, Any],
    types: dict[str, dict[str, str]],
    taken: set[str],
    fetched: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Mapping file body and, per skipped Datadog name, the reason."""
    by_name: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        key = json.dumps([r["otel"], r.get("filter") or {}, r.get("transform") or ""])
        by_name[r["datadog"]].add(key)
    metrics: dict[str, Any] = {}
    skipped: dict[str, str] = {}
    for name in sorted(by_name):
        reason, entry = _entry(name, by_name[name], catalog, types, taken, fetched)
        if entry is None:
            skipped[name] = reason
        else:
            metrics[name] = entry
    body = {"version": 1, "source": "datadog", "labels": LABELS, "metrics": metrics}
    return body, skipped


def _entry(
    name: str,
    candidates: set[str],
    catalog: dict[str, Any],
    types: dict[str, dict[str, str]],
    taken: set[str],
    fetched: str,
) -> tuple[str, dict[str, Any] | None]:
    if name in taken:
        return "already in a mapping file", None
    if len(candidates) != 1:
        return f"{len(candidates)} distinct table targets", None
    otel, flt, transform = json.loads(next(iter(candidates)))
    if transform and not _SCALE.fullmatch(transform):
        return f"transform not supported: {transform}", None
    try:
        scale = float(_SCALE.fullmatch(transform).group(1)) if transform else 1.0  # type: ignore[union-attr]
    except ValueError:
        return f"transform not numeric: {transform}", None
    matchers = {k.replace(".", "_"): v for k, v in sorted(flt.items())}
    if not all(_LABEL.fullmatch(k) for k in matchers):
        return "filter attribute is not a label name", None
    o = catalog.get(otel)
    if o is None:
        return f"{otel} not in the OTel catalog", None
    if o.get("conflicts"):
        return f"{otel} has conflicting OTel definitions: {'; '.join(o['conflicts'])}", None
    dd = types.get(name)
    kind = expected_kind(dd) if dd else None
    if kind is None:
        return "Datadog type unknown", None
    if o["type"] == "gauge" or (o["type"] == "sum" and not o["monotonic"]):
        if kind != "gauge":
            return f"Datadog kind {kind} vs OTel non-cumulative {o['type']}", None  # type: ignore[index]
    elif o["type"] == "sum" and o["monotonic"]:
        if kind != "rate":
            return f"Datadog kind {kind} vs OTel cumulative sum", None  # type: ignore[index]
    else:
        return f"OTel type {o['type']} not supported", None
    assert dd is not None
    source_unit = dd.get("unit_name", "") + (
        f"/{dd['per_unit_name']}" if dd.get("per_unit_name") else ""
    )
    if dd.get("per_unit_name") not in (None, "", "second"):
        return f"Datadog per-unit not supported: {dd['per_unit_name']}", None
    unit_scale = UNIT_SCALES.get((dd.get("unit_name", ""), o["unit"]))
    if unit_scale is None:
        return f"unit pair not supported: {source_unit or '-'} <- {o['unit'] or '-'}", None
    if transform and not math.isclose(scale, unit_scale, rel_tol=1e-12, abs_tol=0.0):
        return f"table scale {scale:g} conflicts with unit scale {unit_scale:g}", None
    scale = unit_scale
    filt = ", ".join(f"{k}: {v}" for k, v in sorted(flt.items()))
    ref = (
        f"Generated by scripts/generate_vendor_mappings.py. Vendor: fixtures/datadog/"
        f"otel-mapping.yaml {name} -> {otel}"
        + (f", filter {filt}" if filt else "")
        + (f", transform {transform}" if transform else "")
        + f" (fetched {fetched}). Datadog: integrations-core {dd['source']} "
        f"{dd['metric_type']}, unit {source_unit or '-'}. OTel: fixtures/otel/catalog.yaml "
        f"{o['type']}{' monotonic' if o['monotonic'] else ''}, unit {o['unit'] or '-'} "
        f"({', '.join(o['sources'])}). Not checked against Dash0 data."
    )
    if not transform and scale != 1:
        ref += f" vendor deviation: table omits scale; explicit unit rule requires {scale:g}."
    entry: dict[str, Any] = {
        "kind": kind,
        "target": {"name": otel, "type": o["type"]},
        "sourceUnit": source_unit,
        "targetUnit": o["unit"] or "",
        "scale": int(scale) if scale.is_integer() else scale,
        "ref": ref,
        "reviewed": None,
    }
    if matchers:
        entry["matchers"] = matchers
    return "", entry


def render(body: dict[str, Any]) -> str:
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def generate(out: Path = OUT) -> tuple[str, dict[str, str]]:
    pin = yaml.safe_load(PIN.read_text(encoding="utf-8"))
    if "filter" not in pin["columns"] or "transform" not in pin["columns"]:
        raise SystemExit("the pin lacks filter/transform columns; re-pin with --all-columns")
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    taken = existing_names(MAPPINGS, out)
    body, skipped = build(pin["rows"], catalog, datadog_types(), taken, pin["fetched"])
    return render(body), skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the output is stale")
    parser.add_argument("--skipped", action="store_true", help="print skipped names and reasons")
    args = parser.parse_args(argv)
    text, skipped = generate()
    count = len(json.loads(text)["metrics"])
    if args.skipped:
        for name, reason in skipped.items():
            print(f"{name}: {reason}")
    if args.check:
        same = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print(f"{'OK' if same else 'STALE'}: {OUT.name} ({count} entries, {len(skipped)} skipped)")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({count} entries, {len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
