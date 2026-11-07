"""The Datadog source provider: dashboards (plans 04/05) and monitors (plan 06)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from migrator.input import InputError, InputFile
from migrator.source.asset import (
    CompileOptions,
    FetchSelection,
    ProviderLoadResult,
    SourceAsset,
)
from migrator.source.datadog.api import fetch_datadog_assets
from migrator.source.datadog.assets import recognize_assets
from migrator.source.datadog.dashboard import compile_dashboard
from migrator.source.datadog.mapping import parse_mapping
from migrator.target import CompileResult, DashboardArtifact, Diagnostic, ItemResult
from migrator.write import assign_slugs


class DatadogProvider:
    @property
    def id(self) -> str:
        return "datadog"

    def load(self, files: list[InputFile]) -> ProviderLoadResult:
        assets, diagnostics = recognize_assets(files)
        return ProviderLoadResult(assets=assets, diagnostics=diagnostics)

    def fetch(self, sel: FetchSelection, env: Mapping[str, str | None], out: str) -> list[str]:
        return fetch_datadog_assets(sel, env, out)

    def compile(
        self, assets: list[SourceAsset], mapping: Any, options: CompileOptions
    ) -> CompileResult:
        parsed = parse_mapping(mapping)
        if not parsed.ok:
            raise InputError("invalid mapping: " + "; ".join(parsed.errors))
        result = CompileResult()
        dashboards = sorted((a for a in assets if a.kind == "dashboard"), key=lambda a: a.source_id)
        slugs = assign_slugs([a.title for a in dashboards])
        for asset, slug in zip(dashboards, slugs, strict=True):
            comp = compile_dashboard(asset, slug, parsed.mapping, options)
            result.items.extend(comp.items)
            result.diagnostics.extend(comp.diagnostics)
            if comp.dashboard is not None:
                result.dashboards.append(DashboardArtifact(slug, asset.source_id, comp.dashboard))
        # Monitors stay on the plan 01 skeleton until plan 06 (Track B) lands compileMonitor.
        for asset in sorted((a for a in assets if a.kind == "monitor"), key=lambda a: a.source_id):
            result.items.append(ItemResult(asset.source_id, "", "monitor", asset.title, "blocked"))
            result.diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_MONITOR_TYPE",
                    severity="error",
                    source_id=asset.source_id,
                    source_path="",
                    message="Monitor conversion is not supported yet.",
                    suggested_action="Wait for monitor support (plan 06) or migrate manually.",
                )
            )
        return result


DATADOG_PROVIDER = DatadogProvider()
