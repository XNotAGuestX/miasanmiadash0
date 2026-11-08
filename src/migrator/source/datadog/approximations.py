"""Approved approximations: the reasons an item may be converted with a remark.

An approximated item is converted, but differs from the source in one documented, minor way.
Its outcome is `approximated` instead of `translated`, and an `APPROXIMATED` warning names the
reason and what differs.

Every reason needs manual approval. A reason whose `approved` is None keeps blocking, exactly
as before it was listed. Only a human reviewer sets `approved`, in the PR that adds or changes
the reason; agents leave it None.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Approval:
    by: str
    date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class Approximation:
    remark: str  # what differs from the source, shown in the APPROXIMATED warning
    evidence: str  # documentation that bounds the difference
    approved: Approval | None


APPROXIMATIONS: dict[str, Approximation] = {
    # D1. Datadog widget `time: {"live_span": X}` pins the widget to its own time frame. Perses
    # panels have no time range of their own: the dashboard `duration` is "the default time
    # range to use on the initial load of the dashboard", and the Panel spec has only display,
    # plugin, queries and links (https://perses.dev/docs/perses/latest/api/dashboard/). When X
    # equals the emitted dashboard duration, the default view is identical; only after the
    # viewer changes the time picker does the panel follow it where Datadog would not.
    "WIDGET_TIME_PIN": Approximation(
        remark=(
            "Widget time pin dropped: it equals the dashboard default range, so the default view "
            "is identical, but the panel follows the time picker where Datadog's widget would not."
        ),
        evidence="https://perses.dev/docs/perses/latest/api/dashboard/",
        approved=None,
    ),
}


def approved(reason: str) -> Approximation | None:
    """The approximation if it is listed and approved, else None (the item keeps blocking)."""
    entry = APPROXIMATIONS.get(reason)
    return entry if entry is not None and entry.approved is not None else None
