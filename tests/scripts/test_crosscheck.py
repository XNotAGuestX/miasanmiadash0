"""Offline tests for scripts/crosscheck.py (Haiku cross-checks of agent0-derived expectations)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

import crosscheck as cc
import verify_common as vc

KEY = "postgres/postgresql_dashboard"  # no rule-blocked requests
RULE_KEY = "nginx/NGINX-Overview_dashboard"  # one request blocked by the rule overlay
SOURCE = "input"  # the W3b subcommand


def ok_source(verdict: str = "pass", reasons: list[str] | None = None) -> dict[str, Any]:
    return {"verdict": verdict, "reasons": reasons or [], "checks": dict.fromkeys(cc.CHECKS, "ok")}


class FakeJudge:
    """Answers from `reply(system, user, schema)` (or a fixed answer); records every call."""

    def __init__(self, reply: Callable[[str, str, dict], Any] | Any = None, model: str = cc.MODEL):
        self.model = model
        self.reply = reply if reply is not None else (lambda s, u, schema: ok_source())
        self.calls: list[tuple[str, str, dict]] = []

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> Any:
        self.calls.append((system, user, schema))
        out = self.reply(system, user, schema) if callable(self.reply) else self.reply
        if isinstance(out, BaseException):
            raise out
        return out


class Scripted(FakeJudge):
    """Returns the scripted answers in order."""

    def __init__(self, answers: list[Any]):
        self.answers = list(answers)
        super().__init__(lambda s, u, schema: self.answers.pop(0))


@pytest.fixture(autouse=True)
def tmp_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    verify = tmp_path / "verify"
    monkeypatch.setattr(vc, "VERIFY_DIR", verify)
    monkeypatch.setattr(vc, "MUTATIONS_DIR", verify / "mutations")
    monkeypatch.setattr(cc, "CACHE_DIR", verify / ".haiku-cache")
    return verify


def verdict_doc(key: str, verifier: str, *, mutations: bool = False) -> dict[str, Any]:
    return yaml.safe_load(vc.verdict_path(key, verifier, mutations=mutations).read_text())


# --------------------------------------------------------------------------- source


def test_source_writes_one_verdict_per_request_in_case_order() -> None:
    judge = FakeJudge()
    assert cc.main([SOURCE, KEY], judge=judge) == 0
    doc = verdict_doc(KEY, "haiku")
    want = [r["source_path"] for r in vc.load_expected(KEY)["requests"]]
    assert [r["source_path"] for r in doc["results"]] == want
    case = vc.load_case(KEY)
    ruled = {r["source_path"] for r in case["requests"] if cc.rule_blocked(r, cc.case_variables(case))}
    assert len(judge.calls) == len(want) - len(ruled)
    assert all(r["verdict"] == "pass" for r in doc["results"])
    assert all(r["method"] == ("rule" if r["source_path"] in ruled else "haiku") for r in doc["results"])
    assert doc["meta"]["model"] == cc.MODEL
    assert doc["meta"]["system_prompt_sha256"] == cc.sha256(cc.source_system_prompt())


def test_source_cache_hit_makes_no_call_and_gives_identical_output() -> None:
    assert cc.main([SOURCE, KEY], judge=FakeJudge(ok_source("nit", ["percent vs ratio"]))) == 0
    first = vc.verdict_path(KEY, "haiku").read_text()
    again = FakeJudge(RuntimeError("must not be called"))
    assert cc.main([SOURCE, KEY], judge=again) == 0
    assert again.calls == []
    assert vc.verdict_path(KEY, "haiku").read_text() == first


def test_cache_key_covers_model_prompt_user_and_schema() -> None:
    call = cc.Call("x", "sys", "user", cc.SOURCE_SCHEMA, cc.validate_source)
    keys = {
        call.cache_key("m1"),
        call.cache_key("m2"),
        cc.Call("x", "sys2", "user", cc.SOURCE_SCHEMA, cc.validate_source).cache_key("m1"),
        cc.Call("x", "sys", "user2", cc.SOURCE_SCHEMA, cc.validate_source).cache_key("m1"),
        cc.Call("x", "sys", "user", cc.RERUN_SCHEMA, cc.validate_source).cache_key("m1"),
    }
    assert len(keys) == 5
    assert call.cache_key("m1") == cc.Call("other label", "sys", "user", cc.SOURCE_SCHEMA, cc.validate_source).cache_key("m1")


def test_rule_blocked_requests_are_decided_without_llm() -> None:
    variables = cc.case_variables(vc.load_case(RULE_KEY))
    case = vc.case_requests(vc.load_case(RULE_KEY))
    rule = {sp for sp, r in case.items() if cc.rule_blocked(r, variables)}
    assert rule  # fixture assumption
    judge = FakeJudge()
    assert cc.main([SOURCE, RULE_KEY], judge=judge) == 0
    results = {r["source_path"]: r for r in verdict_doc(RULE_KEY, "haiku")["results"]}
    assert len(judge.calls) == len(case) - len(rule)
    for sp in rule:
        assert results[sp]["method"] == "rule"
        assert results[sp]["verdict"] == "pass"  # expected.yaml carries the rule's error code


def test_rule_blocked_mutation_flipped_to_translated_is_blocked(tmp_verify: Path) -> None:
    case = vc.load_case(RULE_KEY)
    sp = next(r["source_path"] for r in case["requests"] if cc.rule_blocked(r, cc.case_variables(case)))
    mutations = [
        {"id": "m-flip", "source_path": sp, "mutation": "flip_outcome", "structural": True,
         "expected": {"outcome": "translated", "promql": ['sum({otel_metric_name="nginx.requests"})'], "errors": [], "warnings": []}},
    ]
    (tmp_verify / "mutations" / "nginx").mkdir(parents=True)
    (tmp_verify / "mutations" / f"{RULE_KEY}.yaml").write_text(yaml.safe_dump(mutations))
    judge = FakeJudge()
    assert cc.main([SOURCE, RULE_KEY, "--mutations"], judge=judge) == 0
    assert judge.calls == []
    [row] = verdict_doc(RULE_KEY, "haiku", mutations=True)["results"]
    assert row["source_path"] == "m-flip" and row["verdict"] == "block" and row["method"] == "rule"


def test_mutations_are_keyed_by_mutation_id(tmp_verify: Path) -> None:
    entries = vc.load_expected(KEY)["requests"]
    mutations = [
        {"id": f"m{i}", "source_path": e["source_path"], "mutation": "swap_metric", "structural": False, "expected": e["expected"]}
        for i, e in enumerate(entries[:3])
    ]
    (tmp_verify / "mutations" / "postgres").mkdir(parents=True)
    (tmp_verify / "mutations" / f"{KEY}.yaml").write_text(yaml.safe_dump(mutations))
    judge = FakeJudge(ok_source("block", ["different metric"]))
    assert cc.main([SOURCE, KEY, "--mutations"], judge=judge) == 0
    rows = verdict_doc(KEY, "haiku", mutations=True)["results"]
    assert [r["source_path"] for r in rows] == ["m0", "m1", "m2"]
    assert all(r["verdict"] == "block" for r in rows)
    assert not vc.verdict_path(KEY, "haiku").exists()


def test_schema_invalid_answer_is_asked_again() -> None:
    judge = Scripted([{"verdict": "block", "reasons": [], "checks": dict.fromkeys(cc.CHECKS, "ok")}, ok_source()])
    asker = cc.Asker(judge, retries=2)
    call = cc.Call("x", "sys", "user", cc.SOURCE_SCHEMA, cc.validate_source)
    out, _ = asyncio.run(asker.ask(call))
    assert out["verdict"] == "pass"
    assert len(judge.calls) == 2


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        {"verdict": "maybe", "reasons": [], "checks": dict.fromkeys(cc.CHECKS, "ok")},
        {"verdict": "pass", "reasons": [], "checks": {"quantity": "ok"}},
        {"verdict": "pass", "reasons": [], "checks": dict.fromkeys(cc.CHECKS, "fine")},
        {"verdict": "nit", "reasons": ["  "], "checks": dict.fromkeys(cc.CHECKS, "ok")},
    ],
)
def test_schema_invalid_answers_raise_after_retries(bad: Any) -> None:
    judge = FakeJudge(bad)
    asker = cc.Asker(judge, retries=1)
    call = cc.Call("x", "sys", "user", cc.SOURCE_SCHEMA, cc.validate_source)
    with pytest.raises(cc.InvalidOutput):
        asyncio.run(asker.ask(call))
    assert len(judge.calls) == 2
    assert not cc.CACHE_DIR.exists() or not list(cc.CACHE_DIR.glob("*.json"))  # invalid answers are not cached


def test_invalid_answers_fail_the_dashboard_without_writing() -> None:
    assert cc.main([SOURCE, KEY, "--retries", "0"], judge=FakeJudge({"verdict": "pass"})) == 1
    assert not vc.verdict_path(KEY, "haiku").exists()


def test_prompts_never_name_the_producer() -> None:
    items = cc.plan_source(KEY) + cc.plan_source(RULE_KEY)
    calls = [i.call for i in items if i.call is not None]
    assert calls
    for call in calls:
        assert "agent0" not in (call.system + call.user).lower()
    assert "agent0" not in cc.rerun_system_prompt().lower()


def test_source_prompt_contains_rules_context_and_metric_definitions() -> None:
    item = next(i for i in cc.plan_source(KEY) if i.call is not None)
    assert item.call is not None
    assert "Any Datadog function blocks the whole request" in item.call.system
    user = yaml.safe_load(item.call.user)
    assert set(user) == {"datadog_request", "candidate", "otel_metric_definitions"}
    assert user["datadog_request"]["queries"] == {"query1": "avg:postgresql.rows_fetched{$scope}"}
    assert user["otel_metric_definitions"]["postgresql.tup_fetched"]["type"] == "sum"
    assert user["otel_metric_definitions"]["postgresql.tup_fetched"]["in_dataset"] is True


def test_dry_run_makes_no_calls(capsys: pytest.CaptureFixture[str]) -> None:
    assert cc.main([SOURCE, KEY], judge=FakeJudge()) == 0
    capsys.readouterr()
    assert cc.main([SOURCE, KEY, RULE_KEY, "--dry-run"], judge=FakeJudge(RuntimeError("no"))) == 0
    out = capsys.readouterr().out
    case = vc.load_case(KEY)
    n = len(case["requests"])
    ruled = sum(cc.rule_blocked(r, cc.case_variables(case)) for r in case["requests"])
    calls = n - ruled
    assert f"{KEY}: {n} rows, {ruled} decided without LLM, {calls} Haiku calls ({calls} cached)" in out
    assert "would send" in out  # RULE_KEY is not cached


# --------------------------------------------------------------------------- rerun


@pytest.fixture
def rounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Round 1 = a copy of the committed answers; round 2 = an editable copy."""
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    for d in (r1, r2):
        (d / KEY).mkdir(parents=True)
        shutil.copy(cc.AGENT0_DIR / KEY / "answer.yaml", d / KEY / "answer.yaml")
    monkeypatch.setattr(cc, "AGENT0_DIR", r1)
    return r1, r2


def edit_round2(r2: Path, edit: Callable[[list[dict[str, Any]]], None]) -> None:
    path = r2 / KEY / "answer.yaml"
    items = yaml.safe_load(path.read_text())
    edit(items)
    path.write_text(yaml.safe_dump(items, sort_keys=False))


def translated(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if i["outcome"] == "translated"]


def test_rerun_identical_rounds_make_no_calls(rounds: tuple[Path, Path]) -> None:
    judge = FakeJudge(RuntimeError("must not be called"))
    assert cc.main(["rerun", KEY, "--round2-dir", str(rounds[1])], judge=judge) == 0
    rows = verdict_doc(KEY, "rerun")["results"]
    assert len(rows) == len(vc.load_case(KEY)["requests"])
    assert all(r["verdict"] == "pass" for r in rows)
    assert judge.calls == []


def test_rerun_deterministic_short_circuits(rounds: tuple[Path, Path]) -> None:
    _, r2 = rounds
    marks: dict[str, str] = {}

    def edit(items: list[dict[str, Any]]) -> None:
        t = translated(items)
        missing, flipped, reformatted = t[0], t[1], t[2]
        marks.update(missing=missing["source_path"], flipped=flipped["source_path"], reformatted=reformatted["source_path"])
        items.remove(missing)
        flipped.update(outcome="blocked", promql=None, reason="changed its mind")
        reformatted["promql"] = ["(" + q.replace(", ", ",") + ")" for q in reformatted["promql"]]

    edit_round2(r2, edit)
    judge = FakeJudge(RuntimeError("must not be called"))
    assert cc.main(["rerun", KEY, "--round2-dir", str(r2)], judge=judge) == 0
    rows = {r["source_path"]: r for r in verdict_doc(KEY, "rerun")["results"]}
    assert judge.calls == []
    assert rows[marks["missing"]]["verdict"] == "block"
    assert rows[marks["missing"]]["reasons"][0].startswith("outcome differs between rounds")
    assert rows[marks["flipped"]]["verdict"] == "block"
    assert rows[marks["flipped"]]["reasons"][0].startswith("outcome differs between rounds")
    assert rows[marks["reformatted"]] == {"source_path": marks["reformatted"], "verdict": "pass", "reasons": [], "method": "canonical"}


def test_rerun_overlay_ignores_rule_blocked_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    for d in (r1, r2):
        (d / RULE_KEY).mkdir(parents=True)
        shutil.copy(cc.AGENT0_DIR / RULE_KEY / "answer.yaml", d / RULE_KEY / "answer.yaml")
    monkeypatch.setattr(cc, "AGENT0_DIR", r1)
    variables = cc.case_variables(vc.load_case(RULE_KEY))
    case = vc.case_requests(vc.load_case(RULE_KEY))
    rule = {sp for sp, r in case.items() if cc.rule_blocked(r, variables)}
    path = r2 / RULE_KEY / "answer.yaml"
    items = [i for i in yaml.safe_load(path.read_text()) if i["source_path"] not in rule]  # round 2 dropped them
    path.write_text(yaml.safe_dump(items, sort_keys=False))
    judge = FakeJudge(RuntimeError("must not be called"))
    assert cc.main(["rerun", RULE_KEY, "--round2-dir", str(r2)], judge=judge) == 0
    rows = {r["source_path"]: r for r in verdict_doc(RULE_KEY, "rerun")["results"]}
    for sp in rule:
        assert rows[sp]["verdict"] == "pass" and rows[sp]["method"] == "rule"


@pytest.mark.parametrize(("judgement", "verdict"), [("equivalent", "pass"), ("cosmetic", "nit"), ("semantic", "block")])
def test_rerun_llm_judgement_maps_to_verdict(rounds: tuple[Path, Path], judgement: str, verdict: str) -> None:
    _, r2 = rounds
    changed: list[str] = []

    def edit(items: list[dict[str, Any]]) -> None:
        item = translated(items)[0]
        item["promql"] = ["100 * " + q for q in item["promql"]]
        changed.append(item["source_path"])

    edit_round2(r2, edit)
    judge = FakeJudge({"judgement": judgement, "reason": "scale differs"})
    assert cc.main(["rerun", KEY, "--round2-dir", str(r2)], judge=judge) == 0
    assert len(judge.calls) == 1
    system, user, schema = judge.calls[0]
    assert schema == cc.RERUN_SCHEMA
    assert "agent0" not in (system + user).lower()
    assert set(yaml.safe_load(user)) == {"datadog_request", "candidate_a", "candidate_b", "otel_metric_definitions"}
    row = {r["source_path"]: r for r in verdict_doc(KEY, "rerun")["results"]}[changed[0]]
    assert row["verdict"] == verdict and row["judgement"] == judgement and row["reasons"] == ["scale differs"]


def test_rerun_without_round2_exits_with_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cc.main(["rerun", KEY, "--round2-dir", str(tmp_path / "nope")], judge=FakeJudge()) == 2
    assert "no round-2 answers" in capsys.readouterr().err
    (tmp_path / "empty").mkdir()
    assert cc.main(["rerun", KEY, "--round2-dir", str(tmp_path / "empty")], judge=FakeJudge()) == 2
    assert "no round-2 answers" in capsys.readouterr().err


def test_mutations_flag_requires_source_mode() -> None:
    with pytest.raises(SystemExit):
        cc.parse_args(["rerun", KEY, "--mutations"])
