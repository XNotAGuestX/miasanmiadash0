"""Golden: Postgres monitors (plan 06 Task 5). Regenerate by hand and review the diff."""

from __future__ import annotations

from pathlib import Path

from migrator.cli import main

EXPECTED = Path("fixtures/expected/postgres-monitors")


def tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.relative_to(root).as_posix().startswith("source/")
    }


def test_postgres_monitors_golden(tmp_path: Path) -> None:
    out = tmp_path / "out"
    code = main(
        [
            "convert",
            "--source",
            "datadog",
            "--input",
            "fixtures/datadog/integrations-core/postgres/monitors",
            "--mapping",
            "mappings/datadog/postgres.json",
            "--out",
            str(out),
        ]
    )
    assert code == 2  # one translated, one blocked
    expected, actual = tree(EXPECTED), tree(out)
    assert sorted(actual) == sorted(expected)
    for rel, data in expected.items():
        assert actual[rel] == data, rel
