"""Persisted queue of events for the add-on, delivered with retry and backoff."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .client import AutoLedgerClient, AutoLedgerError
from .const import DOMAIN, OUTBOX_BATCH, OUTBOX_MAX, OUTBOX_RETRY, REPAIR_AFTER

_LOGGER = logging.getLogger(__name__)
ISSUE_UNREACHABLE = "addon_unreachable"


class Outbox:
    def __init__(
        self,
        hass: HomeAssistant,
        client: AutoLedgerClient,
        items: list[dict],
        save: Callable[[], None],
        on_delivered: Callable[[list[dict], dict], None],
    ) -> None:
        self._hass = hass
        self._client = client
        self.items = items  # [{"event": envelope, "queued_at": iso}], shared with the store
        self._save = save
        self._on_delivered = on_delivered
        self._failures = 0
        self._busy = False
        self._retry_unsub: Callable[[], None] | None = None
        self.last_error: str | None = None
        self.last_delivery: datetime | None = None

    @property
    def oldest(self) -> datetime | None:
        return dt_util.parse_datetime(self.items[0]["queued_at"]) if self.items else None

    @callback
    def add(self, envelope: dict) -> None:
        self.items.append({"event": envelope, "queued_at": dt_util.utcnow().isoformat()})
        if len(self.items) > OUTBOX_MAX:
            self._drop_one()
        self._save()
        self.schedule(1)

    def _drop_one(self) -> None:
        """Drop the oldest progress event first; completed records are kept longest."""
        for index, item in enumerate(self.items):
            if item["event"]["type"] == "charge.updated":
                del self.items[index]
                return
        del self.items[0]

    @callback
    def schedule(self, delay: float) -> None:
        if self._retry_unsub is not None:
            return
        self._retry_unsub = async_call_later(self._hass, delay, self._fire)

    @callback
    def cancel(self) -> None:
        if self._retry_unsub is not None:
            self._retry_unsub()
            self._retry_unsub = None

    @callback
    def _fire(self, _now) -> None:
        self._retry_unsub = None
        self._hass.async_create_background_task(self.flush(), f"{DOMAIN} outbox flush")

    async def flush(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            while self.items:
                batch = self.items[:OUTBOX_BATCH]
                try:
                    result = await self._client.ingest([item["event"] for item in batch])
                except AutoLedgerError as err:
                    self._failed(err)
                    return
                del self.items[: len(batch)]
                self._save()
                self._failures = 0
                self.last_error = None
                self.last_delivery = dt_util.utcnow()
                ir.async_delete_issue(self._hass, DOMAIN, ISSUE_UNREACHABLE)
                self._on_delivered(batch, result)
        finally:
            self._busy = False

    def _failed(self, err: AutoLedgerError) -> None:
        self.last_error = str(err)
        delay = OUTBOX_RETRY[min(self._failures, len(OUTBOX_RETRY) - 1)]
        self._failures += 1
        _LOGGER.debug("Delivery failed (%s), %s events waiting, retry in %ss", err, len(self.items), delay)
        oldest = self.oldest
        if oldest is not None and dt_util.utcnow() - oldest > REPAIR_AFTER:
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                ISSUE_UNREACHABLE,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_UNREACHABLE,
                translation_placeholders={"count": str(len(self.items)), "error": str(err)},
            )
        self.schedule(delay)
