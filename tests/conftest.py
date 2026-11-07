"""pytest hooks: oracle-case markers, --include-unreviewed option and the no-network guard."""

from __future__ import annotations

import socket
from typing import Any

import pytest

# --------------------------------------------------------------------------- options

MARKERS = (
    "p0: must pass for the MVP converter (plans 01-04)",
    "p1: dashboard coverage ladder (plan 05)",
    "p2: later coverage (plan 08 services)",
    "unreviewed: expectation not yet confirmed by a human; skipped unless --include-unreviewed",
)


def pytest_configure(config: pytest.Config) -> None:
    for marker in MARKERS:
        config.addinivalue_line("markers", marker)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--include-unreviewed",
        action="store_true",
        default=False,
        help="Also run cases whose expectation has not been confirmed by a human.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--include-unreviewed"):
        return
    skip = pytest.mark.skip(
        reason="expectation not reviewed by a human yet (use --include-unreviewed)"
    )
    for item in items:
        if "unreviewed" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must never touch the network (compiler is offline, AGENTS.md)."""

    def guard(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("network access is not allowed in unit tests")

    monkeypatch.setattr(socket, "socket", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
