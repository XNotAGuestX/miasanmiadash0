"""Shared contract for the oracle verifiers (development time only, issue #87).

Every verifier checks agent0-derived expectations (fixtures/expected/<key>/expected.yaml) and writes
one verdict file per dashboard:

  fixtures/oracle/verify/<svc>/<id>/<verifier>.yaml          verifier in VERIFIERS
  fixtures/oracle/verify/mutations/<svc>/<id>.yaml           known-bad variants (scripts/mutate_expected.py)
  fixtures/oracle/verify/mutations/<svc>/<id>.<verifier>.yaml  the verifier's verdicts on those variants

Verdict file format (YAML):

  # <header comment lines>
  verifier: lint | judge | rerun | haiku
  meta: {...}                      # model, prompt sha256, asked_at, ... (deterministic verifiers: tool only)
  results:
  - source_path: widgets[0].definition.requests[0]   # mutation files: the mutation id instead
    verdict: pass | nit | block
    reasons: [<short strings>]     # required (non-empty) for nit and block
    ...                            # verifier-specific extra keys are allowed

Verdicts are triage signals, never approval: only a human sets `reviewed: true` in overrides.yaml.
Nothing under src/ imports this module and the converter never reads its output (AGENTS.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
VERIFY_DIR = ROOT / "fixtures" / "oracle" / "verify"
MUTATIONS_DIR = VERIFY_DIR / "mutations"
DASHBOARDS_JSON = ROOT / "fixtures" / "oracle" / "dashboards.json"

VERDICTS = ("pass", "nit", "block")
VERIFIERS = ("lint", "judge", "rerun", "haiku")
_RANK = {v: i for i, v in enumerate(VERDICTS)}


class VerdictError(ValueError):
    """A verdict file or result does not follow the contract."""


# --------------------------------------------------------------------------- inputs


def all_keys() -> list[str]:
    """Every case key in fixtures/oracle/dashboards.json, in file order."""
    doc = json.loads(DASHBOARDS_JSON.read_text())
    return [d["case"] for d in doc["dashboards"]]


def load_case(key: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / "fixtures" / "cases" / f"{key}.yaml").read_text())


def load_expected(key: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / "fixtures" / "expected" / key / "expected.yaml").read_text())


def case_requests(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Case requests keyed by source_path, in case order."""
    return {r["source_path"]: r for r in case["requests"]}


def request_context(case: dict[str, Any], source_path: str) -> dict[str, Any]:
    """The Datadog side of one request, as shown to reviewers and LLM verifiers."""
    r = case_requests(case)[source_path]
    return {
        "source_path": source_path,
        "widget": f"{r['widget_type']}: {r['widget_title']}",
        "queries": {q["name"] or "q": q["query"] for q in r["queries"]},
        "formulas": r["formulas"],
        "template_variables": [
            {"name": v["name"], "prefix": v["prefix"], "default": v["default"]} for v in case["template_variables"]
        ],
    }


def candidate(entry: dict[str, Any]) -> dict[str, Any]:
    """The anonymous candidate expectation of one expected.yaml request entry (no provenance)."""
    exp = entry["expected"]
    out: dict[str, Any] = {"outcome": exp["outcome"]}
    if exp["outcome"] == "translated":
        out["promql"] = list(exp.get("promql") or [])
    else:
        out["errors"] = list(exp.get("errors") or [])
    return out


# --------------------------------------------------------------------------- verdicts


def worst(verdicts: list[str]) -> str:
    """The most severe verdict (block > nit > pass); `pass` for an empty list."""
    for v in verdicts:
        if v not in _RANK:
            raise VerdictError(f"unknown verdict {v!r}")
    return max(verdicts, key=_RANK.__getitem__, default="pass")


def check_result(result: dict[str, Any]) -> None:
    if not isinstance(result.get("source_path"), str) or not result["source_path"]:
        raise VerdictError(f"result needs a source_path: {result!r}")
    verdict = result.get("verdict")
    if verdict not in _RANK:
        raise VerdictError(f"{result['source_path']}: verdict must be one of {VERDICTS}, got {verdict!r}")
    reasons = result.get("reasons", [])
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        raise VerdictError(f"{result['source_path']}: reasons must be a list of strings")
    if verdict != "pass" and not reasons:
        raise VerdictError(f"{result['source_path']}: {verdict} needs at least one reason")


def verdict_path(key: str, verifier: str, *, mutations: bool = False) -> Path:
    if verifier not in VERIFIERS:
        raise VerdictError(f"unknown verifier {verifier!r}")
    if mutations:
        return MUTATIONS_DIR / f"{key}.{verifier}.yaml"
    return VERIFY_DIR / key / f"{verifier}.yaml"


def write_verdicts(
    key: str,
    verifier: str,
    results: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
    *,
    header: str = "",
    mutations: bool = False,
    path: Path | None = None,
) -> Path:
    """Validate and write one verdict file. Results keep the given order (callers use case order)."""
    seen: set[str] = set()
    for r in results:
        check_result(r)
        if r["source_path"] in seen:
            raise VerdictError(f"duplicate source_path {r['source_path']!r}")
        seen.add(r["source_path"])
    out = path or verdict_path(key, verifier, mutations=mutations)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {line}" if line else "#" for line in header.strip("\n").splitlines()] if header else []
    lines.append(f"# {verifier} verdicts for {key}. Triage only, never approval: humans set reviewed: true.")
    doc = {"verifier": verifier, "meta": meta or {}, "results": results}
    out.write_text("\n".join(lines) + "\n" + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000))
    return out


def read_verdicts(key: str, verifier: str, *, mutations: bool = False, path: Path | None = None) -> dict[str, dict[str, Any]] | None:
    """Results keyed by source_path, or None when the verifier has not run for this dashboard."""
    p = path or verdict_path(key, verifier, mutations=mutations)
    if not p.is_file():
        return None
    doc = yaml.safe_load(p.read_text())
    if not isinstance(doc, dict) or doc.get("verifier") != verifier or not isinstance(doc.get("results"), list):
        raise VerdictError(f"{p}: not a {verifier} verdict file")
    out: dict[str, dict[str, Any]] = {}
    for r in doc["results"]:
        check_result(r)
        out[r["source_path"]] = r
    return out


def load_mutations(key: str) -> list[dict[str, Any]]:
    """Known-bad variants for one dashboard: [{id, source_path, mutation, expected}], or [] if none."""
    p = MUTATIONS_DIR / f"{key}.yaml"
    if not p.is_file():
        return []
    return yaml.safe_load(p.read_text()) or []
