"""Render the fixed Agent0 oracle prompt for one dashboard (development-time only).

Usage: uv run scripts/render_oracle_prompt.py <service>/<dashboard_id> [dataset]
Writes fixtures/oracle/agent0/<service>/<dashboard_id>/prompt.md and prints it.
Deterministic: same case inventory -> same prompt text.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def render(case_key: str, dataset: str = "default") -> str:
    case = yaml.safe_load((ROOT / "fixtures" / "cases" / f"{case_key}.yaml").read_text())
    template = (ROOT / "fixtures" / "oracle" / "PROMPT.md").read_text()
    body = template.split("\n---\n", 1)[1].strip() + "\n"
    def flow(r: dict) -> str:
        item = {
            "source_path": r["source_path"],
            "widget": f"{r['widget_type']}: {r['widget_title']}",
            "queries": {q["name"] or "q": q["query"] for q in r["queries"]},
            "formulas": r["formulas"],
        }
        return "- " + yaml.safe_dump(item, default_flow_style=True, sort_keys=False, allow_unicode=True, width=100000).strip()

    requests = "\n".join(flow(r) for r in case["requests"])
    values = {
        "{dataset}": dataset,
        "{title}": case["title"],
        "{fixture}": case["source"]["file"],
        "{template_variables}": ", ".join(
            f"${v['name']} (tag `{v['prefix']}`, default `{v['default']}`)" if v["prefix"] else f"${v['name']} (default `{v['default']}`)"
            for v in case["template_variables"]
        )
        or "none",
        "{requests_flow}": requests,
    }
    for key, value in values.items():
        body = body.replace(key, value)
    return body


def main() -> int:
    case_key = sys.argv[1]
    dataset = sys.argv[2] if len(sys.argv) > 2 else "default"
    text = render(case_key, dataset)
    out = ROOT / "fixtures" / "oracle" / "agent0" / case_key / "prompt.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
