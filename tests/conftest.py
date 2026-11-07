"""pytest hooks: --include-unreviewed option and the no-network guard."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make tests/support.py importable

# --------------------------------------------------------------------------- options


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
    skip = pytest.mark.skip(reason="expectation not reviewed by a human yet (use --include-unreviewed)")
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


