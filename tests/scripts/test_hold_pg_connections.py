"""Tests for scripts/hold-pg-connections.sh against a stub `docker` on PATH."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hold-pg-connections.sh"
PASSWORD = "s3cret-pw"


def make_stub(directory: Path, max_conn: int = 100, current: int = 8) -> Path:
    """A stub `docker` that answers the two read-only queries, records every call,
    and for pg_sleep sessions records its pid and sleeps until killed."""
    stub = directory / "docker"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\n\' "$*" >> "{directory}/calls.log"\n'
        'case "$*" in\n'
        f'  *"show max_connections"*) echo {max_conn} ;;\n'
        f'  *"count(*) from pg_stat_activity"*) echo {current} ;;\n'
        "  *pg_terminate_backend*) echo t ;;\n"
        f'  *pg_sleep*) echo $$ > "{directory}/child-$$.pid"; exec sleep 300 ;;\n'
        "esac\n"
    )
    stub.chmod(0o755)
    return directory


def env_for(directory: Path, **overrides: str) -> dict[str, str]:
    env = {
        **os.environ,
        "PATH": f"{directory}{os.pathsep}{os.environ.get('PATH', '')}",
        "PG_CONTAINER": "pg",
        "PGUSER": "u",
        "PGDATABASE": "db",
        "PGPASSWORD": PASSWORD,
    }
    env.update(overrides)
    return env


def run(directory: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SCRIPT), *args],
        env=env_for(directory, **env),
        capture_output=True,
        text=True,
        timeout=30,
    )


def calls(directory: Path) -> str:
    log = directory / "calls.log"
    return log.read_text() if log.exists() else ""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for(cond: Callable[[], bool], seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        time.sleep(0.05)


def test_dry_run_prints_count_sessions(tmp_path: Path) -> None:
    stub = make_stub(tmp_path)
    r = run(stub, "70", "900", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert sum("pg_sleep(900)" in line for line in r.stdout.splitlines()) == 70
    # Dry run only ran the two read-only queries.
    assert len(calls(stub).strip().splitlines()) == 2


def test_never_prints_the_password(tmp_path: Path) -> None:
    stub = make_stub(tmp_path)
    r = run(stub, "2", "10", "--dry-run")
    assert PASSWORD not in r.stdout + r.stderr
    assert PASSWORD not in calls(stub)


def test_refuses_to_exceed_max_connections(tmp_path: Path) -> None:
    stub = make_stub(tmp_path)
    r = run(stub, "95", "60")
    assert r.returncode == 1
    assert "refusing: would exceed max_connections" in r.stderr
    assert not list(stub.glob("child-*"))


@pytest.mark.parametrize("args", [("x", "60"), ("0", "60"), ("2",), ("2", "60", "--nope")])
def test_rejects_bad_arguments(tmp_path: Path, args: tuple[str, ...]) -> None:
    assert run(make_stub(tmp_path), *args).returncode == 1


def test_rejects_missing_container(tmp_path: Path) -> None:
    r = run(make_stub(tmp_path), "2", "60", PG_CONTAINER="")
    assert r.returncode == 1
    assert "PG_CONTAINER" in r.stderr


def test_sigint_cleanup_releases_connections(tmp_path: Path) -> None:
    stub = make_stub(tmp_path)
    proc = subprocess.Popen(
        ["sh", str(SCRIPT), "3", "900"],
        env=env_for(stub),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(lambda: len(list(stub.glob("child-*.pid"))) == 3)
        pids = [int(p.read_text()) for p in stub.glob("child-*.pid")]
        assert all(alive(p) for p in pids)

        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
        wait_for(lambda: not any(alive(p) for p in pids))
        # Server-side sessions are terminated too: killing `docker exec` does not end psql.
        assert "pg_terminate_backend" in calls(stub)
    finally:
        if proc.poll() is None:
            proc.kill()
