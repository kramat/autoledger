"""Snapshot boost: when to ask the car's integration for fresh data (docs/collector.md#snapshot-boost).

Cloud cars upload when they park, but Home Assistant only sees that at the
integration's next poll, which can be hours later. Local hints say when a fresh
report is likely to be waiting in the cloud.
"""

from __future__ import annotations

from datetime import datetime

# Seconds after each hint to refresh. Plugging in at home or leaving home: the
# car's latest report is already in the cloud. Arriving: give the car time to
# upload, and try once more in case it was slow. A stopped charge: the car
# uploads its final battery % shortly after.
HINT_DELAYS: dict[str, tuple[int, ...]] = {
    "charge_started": (0,),
    "charge_stopped": (120,),
    "left_home": (0,),
    "arrived_home": (120, 600),
}
MIN_GAP = 60  # seconds between two refreshes: two phones arriving together give one


def boost_allowed(
    memory: dict, now: datetime, today: str, max_per_day: int, min_gap: float = MIN_GAP
) -> tuple[bool, dict, str]:
    """Whether to refresh now, the new memory, and why not.

    ``memory`` is ``{"day", "count", "last"}`` with ``last`` as an ISO timestamp.
    The count starts again on a new local ``today``.
    """
    count = memory.get("count", 0) if memory.get("day") == today else 0
    if count >= max_per_day:
        return False, memory, f"daily limit of {max_per_day} reached"
    last = datetime.fromisoformat(memory["last"]) if memory.get("last") else None
    if last is not None and 0 <= (now - last).total_seconds() < min_gap:
        return False, memory, "refreshed less than a minute ago"
    return True, {"day": today, "count": count + 1, "last": now.isoformat()}, ""


def presence_hint(old: str | None, new: str | None) -> str | None:
    """``left_home`` / ``arrived_home`` for a person's state change, ignoring unavailable states."""
    unknown = (None, "unavailable", "unknown")
    if old in unknown or new in unknown or old == new:
        return None
    if old == "home":
        return "left_home"
    if new == "home":
        return "arrived_home"
    return None
