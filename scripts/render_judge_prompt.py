"""Render the fixed judge prompt for one dashboard (development time only, issue #87).

Usage: uv run scripts/render_judge_prompt.py <service>/<dashboard_id> [dataset]
Writes fixtures/oracle/verify/<service>/<dashboard_id>/judge.prompt.md and prints it.
Deterministic: same case inventory, expected.yaml, catalog and template -> same prompt text.

The prompt (fixtures/oracle/JUDGE.md) shows every request of fixtures/expected/<key>/expected.yaml,
blocked ones included, as the Datadog side (verify_common.request_context) plus an anonymous
candidate (verify_common.candidate). It names no provenance. scripts/run_oracle.py --mode judge
sends it to Dash0's agent. Nothing under src/ imports this module (AGENTS.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_oracle_prompt  # noqa: E402
import verify_common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "fixtures" / "oracle" / "JUDGE.md"
PROMPT_NAME = "judge.prompt.md"


def _flow(value: object) -> str:
    return yaml.safe_dump(value, default_flow_style=True, sort_keys=False, allow_unicode=True, width=100000).strip()


def request_lines(case: dict, expected: dict) -> list[str]:
    """One YAML list item per case request, in case order: Datadog side first, then the candidate."""
    entries = {e["source_path"]: e for e in expected["requests"]}
    missing = [sp for sp in verify_common.case_requests(case) if sp not in entries]
    if missing:
        raise ValueError(f"expected.yaml has no entry for {len(missing)} request(s): {missing[:3]}")
    lines = []
    for sp in verify_common.case_requests(case):
        datadog = verify_common.request_context(case, sp)
        datadog.pop("source_path")
        datadog.pop("template_variables")  # dashboard-level, shown once above the requests
        lines.append("- " + yaml.safe_dump({"source_path": sp}, allow_unicode=True, width=100000).strip())
        lines.append(f"  datadog: {_flow(datadog)}")
        lines.append(f"  candidate: {_flow(verify_common.candidate(entries[sp]))}")
    return lines


def render(key: str, dataset: str = "default") -> str:
    case = verify_common.load_case(key)
    expected = verify_common.load_expected(key)
    body = TEMPLATE.read_text().split("\n---\n", 1)[1].strip() + "\n"
    values = {
        "{dataset}": dataset,
        "{title}": case["title"],
        "{fixture}": case["source"]["file"],
        "{template_variables}": ", ".join(
            f"${v['name']} (tag `{v['prefix']}`, default `{v['default']}`)" if v["prefix"] else f"${v['name']} (default `{v['default']}`)"
            for v in case["template_variables"]
        )
        or "none",
        "{request_count}": str(len(case["requests"])),
        # Content last, so text inside it is never mistaken for a placeholder.
        "{requests_block}": "\n".join(request_lines(case, expected)),
        "{otel_candidates}": "\n".join(render_oracle_prompt.candidate_lines(case)),
    }
    for placeholder, value in values.items():
        body = body.replace(placeholder, value)
    return body


def prompt_path(key: str, verify_dir: Path | None = None) -> Path:
    return (verify_dir or verify_common.VERIFY_DIR) / key / PROMPT_NAME


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    key = args[0]
    dataset = args[1] if len(args) > 1 else "default"
    text = render(key, dataset)
    out = prompt_path(key)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
