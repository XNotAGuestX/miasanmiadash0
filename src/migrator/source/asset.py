"""The SourceProvider interface and the shapes it exchanges with shared code."""

from __future__ import annotations

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
