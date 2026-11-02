"""Diagnostics download: mapping, detector state and recent decisions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AutoLedgerConfigEntry
from .const import CONF_TOKEN

REDACT = {CONF_TOKEN, "lat", "lon", "latitude", "longitude", "address"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AutoLedgerConfigEntry) -> dict[str, Any]:
    runtime = entry.runtime_data
    outbox = runtime.outbox
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "subentries": {s.subentry_id: {"type": s.subentry_type, "title": s.title, "data": dict(s.data)}
                           for s in entry.subentries.values()},
            "vehicles": runtime.data["vehicles"],
            "chargers": runtime.data["chargers"],
            "outbox": {
                "waiting": len(outbox.items),
                "oldest": outbox.oldest.isoformat() if outbox.oldest else None,
                "last_delivery": outbox.last_delivery.isoformat() if outbox.last_delivery else None,
                "last_error": outbox.last_error,
            },
            "fallback_price": runtime.fallback_price,
            "decisions": list(runtime.decisions),
        },
        REDACT,
    )
