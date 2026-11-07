"""The SourceProvider interface and the shapes it exchanges with shared code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from migrator.input import InputFile
from migrator.target import CompileResult, Diagnostic


@dataclass(frozen=True)
class SourceAsset:
    source_id: str
    kind: Literal["dashboard", "monitor"]
    title: str
    raw: Any
    body: dict[str, Any]


@dataclass(frozen=True)
class CompileOptions:
    project: str = "datadog-migration"


@dataclass(frozen=True)
class FetchSelection:
    """Explicit IDs to fetch from a source API (plan 10)."""

    dashboard_ids: tuple[str, ...] = ()
    monitor_ids: tuple[str, ...] = ()


@dataclass
class ProviderLoadResult:
    assets: list[SourceAsset] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


class SourceProvider(Protocol):
    @property
    def id(self) -> str: ...

    def load(self, files: list[InputFile]) -> ProviderLoadResult: ...

    def compile(
        self, assets: list[SourceAsset], mapping: Any, options: CompileOptions
    ) -> CompileResult: ...


class FetchingProvider(SourceProvider, Protocol):
    """A provider that can also fetch assets from its API by explicit ID (optional)."""

    def fetch(self, sel: FetchSelection, env: Mapping[str, str | None], out: str) -> list[str]: ...
