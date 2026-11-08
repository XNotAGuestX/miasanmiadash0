"""Datadog mapping file contract (handoff plans 03, 05 and 06; several files: issue #123).

Every metric and label pair the compiler uses comes from the mapping files. Only a human may
set ``reviewed``; coding assistants leave it ``null``. A file may set top-level ``labels``:
an entry without its own ``labels`` inherits them; an entry's own ``labels`` replace them whole.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

Label = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]
Scale = Annotated[float, Field(gt=0, allow_inf_nan=False)]
# A fixed PromQL range such as "5m". Used by RateMapping.rateWindow (issue #90).
RangeDuration = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*[smh]$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Reviewed(_Strict):
    by: NonEmpty
    date: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    evidence: NonEmpty


class GaugeTarget(_Strict):
    name: NonEmpty
    type: Literal["gauge", "sum"]


class RateTarget(_Strict):
    name: NonEmpty
    type: Literal["sum"]


class Grain(_Strict):
    labels: Annotated[list[Label], Field(min_length=1)]
    aggregation: Literal["avg", "max", "min", "sum"]


class GaugeMapping(_Strict):
    kind: Literal["gauge"]
    target: GaugeTarget
    sourceUnit: str
    targetUnit: str
    scale: Scale
    labels: dict[str, Label]
    matchers: dict[Label, str] = Field(default_factory=dict)
    grain: Grain | None = None
    ref: NonEmpty
    reviewed: Reviewed | None


class RateMapping(_Strict):
    kind: Literal["rate"]
    target: RateTarget
    sourceUnit: str
    targetUnit: str
    scale: Scale
    labels: dict[str, Label]
    matchers: dict[Label, str] = Field(default_factory=dict)
    grain: Grain | None = None
    # A fixed rate() range, used instead of $__rate_interval. For metrics reported
    # too rarely for Dash0's $__rate_interval (e.g. every 60 s): rate() needs at least
    # two samples in its range. Set it from the measured collection interval, as part
    # of the reviewed entry (issue #90).
    rateWindow: RangeDuration | None = None
    ref: NonEmpty
    reviewed: Reviewed | None


class ExpressionMapping(_Strict):
    kind: Literal["expression"]
    expression: NonEmpty
    outputLabels: list[Label]
    labels: dict[str, Label]
    sourceUnit: str
    targetUnit: str
    scale: Scale
    ref: NonEmpty
    reviewed: Reviewed | None

    @field_validator("expression")
    @classmethod
    def _requires_filters_placeholder(cls, value: str) -> str:
        if "$filters" not in value:
            raise ValueError("expression must contain the literal $filters placeholder")
        return value


MetricMapping = GaugeMapping | RateMapping | ExpressionMapping

_KINDS: dict[str, type[GaugeMapping] | type[RateMapping] | type[ExpressionMapping]] = {
    "gauge": GaugeMapping,
    "rate": RateMapping,
    "expression": ExpressionMapping,
}


class _Envelope(_Strict):
    version: Literal[1]
    source: Literal["datadog"]
    # File-level default for entries without their own `labels`.
    labels: dict[str, Label] | None = None
    metrics: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class DatadogMapping:
    version: int
    source: str
    metrics: dict[str, MetricMapping]


@dataclass(frozen=True)
class MappingOk:
    mapping: DatadogMapping
    ok: Literal[True] = True


@dataclass(frozen=True)
class MappingInvalid:
    errors: list[str]
    ok: Literal[False] = False


def _format(prefix: list[str], err: ValidationError) -> list[str]:
    out = []
    for e in err.errors():
        path = ".".join(prefix + [str(p) for p in e["loc"]])
        out.append(f"{path}: {e['msg']}")
    return out


def parse_mapping(raw: Any) -> MappingOk | MappingInvalid:
    try:
        envelope = _Envelope.model_validate(raw)
    except ValidationError as err:
        return MappingInvalid(errors=_format([], err))
    errors: list[str] = []
    metrics: dict[str, MetricMapping] = {}
    for name in sorted(envelope.metrics):
        entry = envelope.metrics[name]
        kind = entry.get("kind")
        model = _KINDS.get(kind) if isinstance(kind, str) else None
        if model is None:
            known = ", ".join(sorted(_KINDS))
            errors.append(f"metrics.{name}.kind: unknown kind {kind!r}; known: {known}")
            continue
        if "labels" not in entry and envelope.labels is not None:
            entry = {**entry, "labels": envelope.labels}
        try:
            metrics[name] = model.model_validate(entry)
        except ValidationError as err:
            errors.extend(_format(["metrics", name], err))
    if errors:
        return MappingInvalid(errors=errors)
    return MappingOk(
        mapping=DatadogMapping(version=envelope.version, source=envelope.source, metrics=metrics)
    )


def parse_mappings(files: Sequence[tuple[str, Any]]) -> MappingOk | MappingInvalid:
    """Parse several mapping files, given as (file name, raw JSON), into one table.

    A metric defined in two files is an error naming both files. Errors are prefixed
    with the file name."""
    if not files:
        return MappingInvalid(errors=["no mapping files"])
    errors: list[str] = []
    owner: dict[str, str] = {}
    metrics: dict[str, MetricMapping] = {}
    for source_id, raw in files:
        parsed = parse_mapping(raw)
        if not parsed.ok:
            errors.extend(f"{source_id}: {e}" for e in parsed.errors)
            continue
        for name, entry in parsed.mapping.metrics.items():
            if name in owner:
                errors.append(f"metrics.{name}: defined in both {owner[name]} and {source_id}")
                continue
            owner[name] = source_id
            metrics[name] = entry
    if errors:
        return MappingInvalid(errors=errors)
    return MappingOk(
        mapping=DatadogMapping(version=1, source="datadog", metrics=dict(sorted(metrics.items())))
    )
