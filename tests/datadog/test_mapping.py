import json
from pathlib import Path

from migrator.source.datadog.mapping import MappingInvalid, parse_mapping
from tests.datadog.helpers import entry, raw_mapping


def errors(raw: object) -> list[str]:
    r = parse_mapping(raw)
    assert isinstance(r, MappingInvalid), r
    return r.errors


def test_accepts_a_minimal_gauge_entry() -> None:
    assert parse_mapping(raw_mapping(**{"postgresql.connections": entry(reviewed=None)})).ok


def test_rejects_dotted_label_names() -> None:
    errs = errors(raw_mapping(**{"postgresql.connections": entry(labels={"db": "db.namespace"})}))
    assert any(e.startswith("metrics.postgresql.connections.labels.db:") for e in errs)


def test_rejects_unknown_kind() -> None:
    assert errors(raw_mapping(x=entry(kind="histogram")))


def test_rejects_wrong_source() -> None:
    assert errors({"version": 1, "source": "grafana", "metrics": {}})


def test_rejects_unknown_keys() -> None:
    assert errors(raw_mapping(x=entry(foo=1)))
    assert errors({"version": 1, "source": "datadog", "metrics": {}, "foo": 1})


def test_rate_requires_sum_target() -> None:
    assert errors(raw_mapping(x=entry(kind="rate", target={"name": "a", "type": "gauge"})))


def test_rejects_non_finite_or_non_positive_scale() -> None:
    assert errors(raw_mapping(x=entry(scale=0)))
    assert errors(raw_mapping(x=entry(scale=-1)))


def test_rejects_bad_matcher_and_grain_labels() -> None:
    assert errors(raw_mapping(x=entry(matchers={"a.b": "c"})))
    assert errors(raw_mapping(x=entry(grain={"labels": ["a.b"], "aggregation": "max"})))
    assert errors(raw_mapping(x=entry(grain={"labels": ["a"], "aggregation": "count"})))


def test_every_mapping_file_parses() -> None:
    files = sorted(Path("mappings/datadog").glob("*.json"))
    assert files
    for f in files:
        r = parse_mapping(json.loads(f.read_text()))
        assert r.ok, (f, getattr(r, "errors", None))


def test_mapping_entries_state_review_explicitly() -> None:
    # Every entry carries `reviewed` (null until a human reviews it).
    for f in sorted(Path("mappings/datadog").glob("*.json")):
        for name, e in json.loads(f.read_text())["metrics"].items():
            assert "reviewed" in e, (f, name)
