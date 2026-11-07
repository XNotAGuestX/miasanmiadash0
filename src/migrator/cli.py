"""Single entry point for every project command: ``uv run migrator <command>``.

Commands:
  convert    offline Datadog -> Perses conversion (exit 0 / 2 / 1)
  test       run the test suite (extra arguments go to pytest)
  typecheck  run mypy over src and tests
  lint       run ruff over src and tests
  check      lint + typecheck + test
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from migrator.input import InputError

_DEV_TOOLS_HINT = "dev tools missing; run `uv sync` first"


def _cmd_convert(args: argparse.Namespace) -> int:
    from migrator.convert import ConvertOptions, run_convert
    from migrator.report import format_summary

    try:
        result = run_convert(
            ConvertOptions(
                source=args.source,
                inputs=args.input,
                mapping=args.mapping,
                out=args.out,
                format=args.format,
                project=args.project,
            )
        )
    except InputError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(format_summary(result.report, result.slugs))
    return result.exit_code


def _run_tool(argv: list[str]) -> int:
    try:
        return subprocess.call([sys.executable, "-m", *argv])
    except FileNotFoundError:
        print(f"error: {_DEV_TOOLS_HINT}", file=sys.stderr)
        return 1


def _cmd_test(args: argparse.Namespace, extra: list[str]) -> int:
    return _run_tool(["pytest", *extra])


def _cmd_typecheck(args: argparse.Namespace, extra: list[str]) -> int:
    return _run_tool(["mypy", "src", "tests", *extra])


def _cmd_lint(args: argparse.Namespace, extra: list[str]) -> int:
    return _run_tool(["ruff", "check", "src", "tests", *extra])


def _cmd_check(args: argparse.Namespace, extra: list[str]) -> int:
    for step in (_cmd_lint, _cmd_typecheck, _cmd_test):
        code = step(args, [])
        if code != 0:
            return code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="migrator", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    conv = sub.add_parser("convert", help="convert source dashboards to Perses (offline)")
    conv.add_argument("--source", required=True, help="source provider id, e.g. datadog")
    conv.add_argument("--input", required=True, nargs="+", help="input files or folders")
    conv.add_argument("--mapping", required=True, help="reviewed mapping file (JSON)")
    conv.add_argument("--out", required=True, help="output directory (must be empty)")
    conv.add_argument("--format", choices=["json", "yaml"], default="json")
    conv.add_argument("--project", default="datadog-migration", help="Perses project name")

    sub.add_parser("test", help="run the test suite; extra args go to pytest")
    sub.add_parser("typecheck", help="run mypy")
    sub.add_parser("lint", help="run ruff")
    sub.add_parser("check", help="lint, typecheck and test")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    passthrough = {
        "test": _cmd_test,
        "typecheck": _cmd_typecheck,
        "lint": _cmd_lint,
        "check": _cmd_check,
    }
    if argv and argv[0] in passthrough:
        args, extra = parser.parse_known_args(argv[:1])
        return passthrough[argv[0]](args, argv[1:])
    args = parser.parse_args(argv)
    return _cmd_convert(args)


if __name__ == "__main__":
    sys.exit(main())
