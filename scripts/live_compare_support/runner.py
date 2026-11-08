"""One-shot orchestration, read-back evidence and resumable publication."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import operator
import os
import re
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import promql_parser as prom
from pydantic import ValidationError

from live_compare_support.comparison import DataError, Series, compare
from live_compare_support.config import (
    ROOT,
    Case,
    Suite,
    Workload,
    load,
    read_json,
    resolve,
    save_json,
)
from live_compare_support.environment import Environment
from live_compare_support.queries import BoundQuery, pair, query_source, query_target
from migrator.convert import ConvertOptions, run_convert
from migrator.destination.dash0 import Dash0Config, read_back, read_dash0_config
from migrator.http import HttpSend, urllib_send
from migrator.input import InputError
from migrator.publish import PublishOptions, run_publish
from migrator.receipts import load_receipts
from migrator.source.datadog.api import read_datadog_config

EnvironmentFactory = Callable[..., Environment]


def compile_suite(suite: Suite, config: Path, directory: Path) -> None:
    run_convert(
        ConvertOptions(
            "datadog",
            [str(resolve(config, p)) for p in suite.inputs],
            [str(resolve(config, p)) for p in suite.mappings],
            str(directory),
        )
    )


def artifact(root: Path, case: Case) -> tuple[str, Any, Any]:
    manifest = read_json(root / "manifest.json")
    kind = "dashboard" if case.kind == "dashboard" else "check-rule"
    entries = [e for e in manifest["entries"] if e["sourceId"] == case.source and e["kind"] == kind]
    sources = [
        e for e in manifest["entries"] if e["sourceId"] == case.source and e["kind"] == "source"
    ]
    if len(sources) != 1:
        raise InputError(f"case {case.id}: sourceId is missing or ambiguous")
    if len(entries) != 1 or entries[0]["outcome"] != "translated":
        raise DataError(
            f"case {case.id}: conversion is blocked or partial; inspect compiled/report.json"
        )
    entry = entries[0]
    for item in [sources[0], entry]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise InputError("manifest path escapes compiled directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("compiled artifact hash mismatch")
    return entry["path"], read_json(root / sources[0]["path"]), read_json(root / entry["path"])


def bind_case(root: Path, case: Case, suite: Suite, run_id: str) -> tuple[str, BoundQuery]:
    path, source, target = artifact(root, case)
    try:
        bound = pair(case, source, target, suite.rate_interval, run_id)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise InputError(
            f"case {case.id}: invalid source/target reference ({type(err).__name__})"
        ) from None
    if bound.monitor_window and (
        bound.monitor_window % suite.step_seconds or suite.warmup_seconds < bound.monitor_window
    ):
        raise InputError("monitor window must align to step and fit within warm-up")
    return path, bound


def validate_readback(expected: Any, actual: Any, kind: str, prefix: str) -> bool:
    expected = copy.deepcopy(expected)
    if not isinstance(actual, dict):
        return False
    if "dash0.com/deleted-at" in actual.get("metadata", {}).get("annotations", {}):
        return False
    if kind == "dashboard":
        expected["metadata"]["name"] = prefix + expected["metadata"]["name"]
        expected["spec"]["display"]["name"] = prefix + expected["spec"]["display"]["name"]
        metadata = actual.get("metadata", {})
        return (
            actual.get("kind") == "Dashboard"
            and actual.get("spec") == expected["spec"]
            and metadata.get("name") == expected["metadata"]["name"]
            and metadata.get("project") == expected["metadata"]["project"]
            and "dash0.com/deleted-at" not in metadata.get("annotations", {})
        )
    expected["name"] = prefix + expected["name"]
    if expected.get("enabled") is not False or actual.get("enabled") is not False:
        return False
    for key, value in expected.items():
        if key in ("interval", "for"):
            if actual.get(key) == value:
                continue
            try:
                if prom.parse_duration(value) != prom.parse_duration(actual.get(key, "")):
                    return False
            except ValueError:
                return False
        elif actual.get(key) != value:
            return False
    return True


def read_assets(
    root: Path, cfg: Dash0Config, prefix: str, send: HttpSend
) -> tuple[dict[str, Any], list[Any]]:
    remote = {}
    evidence = []
    entries = {e["path"]: e for e in read_json(root / "manifest.json")["entries"]}
    for receipt in load_receipts(root):
        if receipt.status != "imported" or not receipt.id:
            raise RuntimeError(
                "publication has a failed/unknown receipt; reconcile before resuming"
            )
        if (receipt.api_url, receipt.dataset, receipt.name_prefix) != (
            cfg.api_url,
            cfg.dataset,
            prefix,
        ):
            raise InputError("receipt belongs to another destination or name prefix")
        kind = entries[receipt.path]["kind"]
        if kind not in ("dashboard", "check-rule"):
            raise InputError("unexpected receipt kind")
        actual = read_back(kind, receipt.id, cfg, send)
        valid = validate_readback(read_json(root / receipt.path), actual, kind, prefix)
        evidence.append(
            {"path": receipt.path, "id": receipt.id, "readback": "passed" if valid else "failed"}
        )
        if valid:
            remote[receipt.path] = actual
    return remote, evidence


def monitor_values(
    series: list[Series], bound: BoundQuery, times: list[int], step: int
) -> list[Series]:
    reducers: dict[str, Callable[[list[float]], float]] = {
        "avg": lambda v: sum(v) / len(v),
        "min": min,
        "max": max,
        "sum": sum,
    }
    out = []
    expected = set(range(times[0] - bound.monitor_window + step, times[-1] + step, step))
    for s in series:
        if set(s.samples) != expected:
            raise DataError("monitor source lookback has incomplete coverage")
        values = {
            t: reducers[bound.monitor_aggregator](
                [s.samples[x] for x in range(t - bound.monitor_window + step, t + step, step)]
            )
            for t in times
        }
        out.append(Series(s.labels, values))
    return out


def threshold_decisions(series: list[Series], bound: BoundQuery) -> list[Series]:
    operations = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
    thresholds = bound.thresholds or {}
    # Encode each threshold independently; a critical/degraded mismatch is never
    # hidden by numeric averaging or tolerance.
    out = []
    for s in series:
        for name, threshold in sorted(thresholds.items()):
            out.append(
                Series(
                    {**s.labels, "threshold": name},
                    {
                        t: float(operations[bound.comparator](v, threshold))
                        for t, v in s.samples.items()
                    },
                )
            )
    return out


def redact(message: str, env: Mapping[str, str]) -> str:
    for name in ["DD_API_KEY", "DD_APP_KEY", "DASH0_AUTH_TOKEN"]:
        if env.get(name):
            message = message.replace(env[name], "<redacted>")
    return message[:800]


def write_evidence(out: Path, report: dict[str, Any]) -> None:
    save_json(out / "comparison.json", report)
    lines = [
        "# Live comparison",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Dataset: `{report['dataset']}`; run: `{report['runId']}`",
        "",
        "| Case | Result | Details |",
        "|---|---|---|",
    ]
    for case in report["cases"]:
        detail = case.get("error", f"{len(case.get('series', []))} matched series")
        lines.append(f"| {case['id']} | {case['status']} | {detail.replace('|', '/')} |")
    if report.get("window"):
        lines.extend(["", f"UTC Unix-second window: `{report['window']}`."])
    for case in report["cases"]:
        if case.get("executedTarget"):
            lines.extend(
                [
                    "",
                    f"## {case['id']}",
                    "",
                    "Datadog queries:",
                    "```json",
                    json.dumps(case["sourceQueries"], indent=2),
                    "```",
                    f"Formula: `{case['sourceFormula']}`",
                    "",
                    "Dash0 scoped expression:",
                    "```promql",
                    case["executedTarget"],
                    "```",
                    f"Mode: `{case['mode']}`; relative tolerance "
                    f"{case['relativeTolerancePct']}%; absolute tolerance "
                    f"{case['absoluteTolerance']}.",
                ]
            )
        for s in case.get("series", []):
            lines.extend(
                [
                    "",
                    f"- `{case['id']}` {s['labels']}: Datadog {s['source']}; "
                    f"Dash0 {s['destination']}; coverage {s['coverage']:.0%}; "
                    f"maximum difference {s['maxAbsoluteDifference']:.6g}.",
                ]
            )
        if case.get("thresholdDecisions"):
            lines.extend(["", "Threshold decisions: " + case["thresholdDecisions"]["status"]])
    lines.extend(["", "Asset read-back:"])
    for asset in report.get("assets", []):
        lines.append(f"- `{asset['path']}`: `{asset['id']}` — {asset['readback']}")
    if report.get("error"):
        lines.extend(["", report["error"]])
    lines.extend(["", "Checks remain disabled. This evidence covers only the selected cases."])
    (out / "comparison.md").write_text("\n".join(lines) + "\n")


def fingerprint(
    workload: Workload,
    suite: Suite,
    profile: Path,
    scratch: Path,
    dataset: str,
    env: Mapping[str, str],
    selected: list[str],
) -> str:
    parts = [
        json.dumps(
            [
                workload.model_dump(),
                suite.model_dump(),
                dataset,
                selected,
                env.get("DD_SITE", "datadoghq.eu"),
                env.get("DASH0_API_URL"),
                env.get("DASH0_OTLP_ENDPOINT"),
            ],
            sort_keys=True,
        ).encode(),
        (ROOT / "scripts/live/images.lock.json").read_bytes(),
    ]
    parts.extend(p.read_bytes() for p in sorted(scratch.rglob("*")) if p.is_file())
    parts.extend(resolve(profile, p).read_bytes() for p in workload.seed_sql)
    if workload.feature_flags:
        parts.append(resolve(profile, workload.feature_flags).read_bytes())
    return hashlib.sha256(b"\0".join(parts)).hexdigest()


def execute(
    args: argparse.Namespace,
    env: Mapping[str, str],
    send: HttpSend,
    make_environment: EnvironmentFactory,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> int:
    workload, suite = load(args.dataset_config, Workload), load(args.tests, Suite)
    for p in workload.seed_sql:
        if not resolve(args.dataset_config, p).is_file():
            raise InputError("seed SQL file missing")
    if workload.feature_flags:
        flags = read_json(resolve(args.dataset_config, workload.feature_flags))
        if not isinstance(flags, dict) or not isinstance(flags.get("flags"), dict):
            raise InputError("feature_flags must be a flagd JSON document")
    chosen = set(args.case or [c.id for c in suite.cases])
    if not chosen <= {c.id for c in suite.cases}:
        raise InputError("unknown --case id")
    cases = [c for c in suite.cases if c.id in chosen]
    with tempfile.TemporaryDirectory(prefix="live-compare-") as temp:
        scratch = Path(temp) / "compiled"
        compile_suite(suite, args.tests, scratch)
        blocked: list[dict[str, Any]] = []
        for case in cases:
            try:
                bind_case(scratch, case, suite, "demo-live-dry-run")
            except DataError as err:
                blocked.append({"id": case.id, "status": "blocked", "error": str(err)})
        if args.dry_run:
            print(
                f"DRY-RUN: {len(cases)} cases, {len(blocked)} blocked; "
                "no containers started or vendor requests sent"
            )
            for item in blocked:
                print(item["error"])
            return 2 if blocked else 0
        run_env = dict(env)
        run_env["DASH0_DATASET"] = args.dash0_dataset
        run_env.setdefault("DD_SITE", "datadoghq.eu")
        cfg, dd = read_dash0_config(run_env), read_datadog_config(run_env)
        for name in ["DASH0_API_URL", "DASH0_OTLP_ENDPOINT"]:
            url = urlsplit(run_env.get(name, ""))
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username is not None
                or url.query
                or url.fragment
            ):
                raise InputError(
                    f"{name} must be an explicit HTTPS endpoint without credentials/query"
                )
        digest = fingerprint(
            workload, suite, args.dataset_config, scratch, cfg.dataset, run_env, sorted(chosen)
        )
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        with (out / ".lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise InputError("another process owns this run directory") from None
            state_path = out / "state.json"
            if state_path.exists():
                state = read_json(state_path)
                if state["configDigest"] != digest:
                    raise InputError(
                        "run inputs/configuration/destination changed; use a new --out"
                    )
                if not re.fullmatch(r"demo-live-[a-f0-9]{12}", state["runId"]):
                    raise InputError("invalid saved run identifier")
                if state.get("publicationInFlight"):
                    raise InputError(
                        "previous publication was interrupted; reconcile Dash0 and "
                        "receipts before clearing publicationInFlight in state.json"
                    )
            else:
                if any(p.name != ".lock" for p in out.iterdir()):
                    raise InputError("output directory is not a live comparison run")
                state = {
                    "runId": "demo-live-" + uuid.uuid4().hex[:12],
                    "configDigest": digest,
                    "collectionComplete": False,
                    "publicationInFlight": False,
                }
                save_json(state_path, state)
            compiled = out / "compiled"
            if not compiled.exists():
                import shutil

                shutil.copytree(scratch, compiled)
            else:
                for file in scratch.rglob("*"):
                    if (
                        file.is_file()
                        and (compiled / file.relative_to(scratch)).read_bytes() != file.read_bytes()
                    ):
                        raise InputError("saved conversion artifacts were modified")
            run_id = state["runId"]
            environment = make_environment(
                out / "runtime", workload, args.dataset_config, run_id, run_env
            )
            report: dict[str, Any] = {
                "version": 1,
                "runId": run_id,
                "dataset": cfg.dataset,
                "status": "failed",
                "assets": [],
                "cases": blocked,
            }
            operational_error = False
            try:
                if len(blocked) == len(cases):
                    report["status"] = "blocked"
                    return 2
                first = next(c for c in cases if c.id not in {b["id"] for b in blocked})
                _, preflight = bind_case(compiled, first, suite, run_id)
                # Auth/dataset checks happen before containers or publication.
                end_probe = int(now()) // suite.step_seconds * suite.step_seconds
                query_source(
                    preflight,
                    end_probe - suite.step_seconds,
                    end_probe,
                    suite.step_seconds,
                    dd,
                    send,
                )
                query_target(
                    preflight,
                    end_probe - suite.step_seconds,
                    end_probe,
                    suite.step_seconds,
                    cfg,
                    send,
                )
                if not state["collectionComplete"]:
                    environment.stop()  # clean up only this run after a previous interruption
                    environment.prepare()
                    environment.start()
                    start = (
                        math.ceil((now() + suite.warmup_seconds) / suite.step_seconds)
                        * suite.step_seconds
                    )
                    state.update(start=start, end=start + suite.window_seconds)
                    save_json(state_path, state)
                    until = state["end"] + suite.settle_seconds
                    while now() < until:
                        remaining = until - now()
                        print(
                            f"Collecting shared samples: {math.ceil(remaining)}s remaining",
                            flush=True,
                        )
                        sleep(min(30, remaining))
                    state["collectionComplete"] = True
                    save_json(state_path, state)
                report["window"] = {
                    "start": state["start"],
                    "endExclusive": state["end"],
                    "step": suite.step_seconds,
                }
                state["publicationInFlight"] = True
                save_json(state_path, state)
                published = run_publish(
                    PublishOptions(str(compiled), name_prefix=run_id + "-"), run_env, send
                )
                state["publicationInFlight"] = False
                save_json(state_path, state)
                report["publicationExitCode"] = published.exit_code
                report["conversionSummary"] = read_json(compiled / "report.json")["summary"]
                if published.exit_code == 1:
                    raise RuntimeError(
                        "publication failed or is ambiguous; inspect local import-results.json"
                    )
                remote, report["assets"] = read_assets(compiled, cfg, run_id + "-", send)
                times = list(range(state["start"], state["end"], suite.step_seconds))
                for case in cases:
                    if case.id in {b["id"] for b in blocked}:
                        continue
                    result: dict[str, Any] = {
                        "id": case.id,
                        "mode": case.mode,
                        "relativeTolerancePct": case.relative_tolerance_pct,
                        "absoluteTolerance": case.absolute_tolerance,
                    }
                    try:
                        path, _ = bind_case(compiled, case, suite, run_id)
                        if path not in remote:
                            raise DataError("published asset read-back failed or receipt missing")
                        _, source, _ = artifact(compiled, case)
                        bound = pair(case, source, remote[path], suite.rate_interval, run_id)
                        result.update(
                            sourceQueries=bound.queries,
                            sourceFormula=bound.formula,
                            executedTarget=bound.target,
                            artifact=path,
                        )
                        lookback = max(0, bound.monitor_window - suite.step_seconds)
                        a = query_source(
                            bound, times[0] - lookback, state["end"], suite.step_seconds, dd, send
                        )
                        b = query_target(
                            bound, times[0], state["end"], suite.step_seconds, cfg, send
                        )
                        if bound.monitor_window:
                            a = monitor_values(a, bound, times, suite.step_seconds)
                        result.update(compare(case, a, b, times))
                        if bound.thresholds:
                            decision_case = case.model_copy(
                                update={
                                    "mode": "per_bucket",
                                    "relative_tolerance_pct": 0,
                                    "absolute_tolerance": 0,
                                    "require_nonzero": False,
                                    "series_labels": {
                                        **case.series_labels,
                                        "threshold": "threshold",
                                    },
                                }
                            )
                            decisions = compare(
                                decision_case,
                                threshold_decisions(a, bound),
                                threshold_decisions(b, bound),
                                times,
                            )
                            result["thresholdDecisions"] = decisions
                            if decisions["status"] != "passed":
                                result["status"] = "failed"
                    except DataError as err:
                        result.update(status="failed", error=str(err))
                    except RuntimeError as err:
                        operational_error = True
                        result.update(status="error", error=redact(str(err), run_env))
                    report["cases"].append(result)
                    print(f"{case.id}: {result['status']}", flush=True)
                report["status"] = (
                    "passed"
                    if (
                        published.exit_code == 0
                        and all(c["status"] == "passed" for c in report["cases"])
                        and all(a["readback"] == "passed" for a in report["assets"])
                    )
                    else "failed"
                )
            except (Exception, KeyboardInterrupt) as err:
                operational_error = True
                report["error"] = redact(
                    "interrupted" if isinstance(err, KeyboardInterrupt) else str(err), run_env
                )
            finally:
                if not args.keep_running:
                    try:
                        environment.stop()
                        report["containers"] = "stopped"
                    except (Exception, KeyboardInterrupt):
                        operational_error = True
                        report.update(status="failed", cleanupError="container cleanup failed")
                else:
                    report["containers"] = "retained"
                write_evidence(out, report)
            return 1 if operational_error else (0 if report["status"] == "passed" else 2)


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    send: HttpSend = urllib_send,
    make_environment: EnvironmentFactory = Environment,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description="On-demand Datadog → Dash0 live comparison")
    parser.add_argument("--dataset-config", required=True, type=Path)
    parser.add_argument("--tests", required=True, type=Path)
    parser.add_argument("--dash0-dataset", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--case", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-running", action="store_true")
    args = parser.parse_args(argv)
    environment = dict(os.environ if env is None else env)
    try:
        if not args.dash0_dataset.strip():
            raise InputError("--dash0-dataset must be nonempty")
        return execute(args, environment, send, make_environment, now, sleep)
    except DataError as err:
        print(f"blocked: {redact(str(err), environment)}")
        return 2
    except (OSError, InputError, ValueError, ValidationError, RuntimeError) as err:
        print(f"error: {redact(str(err), environment)}")
        return 1
