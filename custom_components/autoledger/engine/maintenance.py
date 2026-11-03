"""Which maintenance items need an ``autoledger_maintenance_due`` event."""

from __future__ import annotations

NOTIFY_STATUSES = ("soon", "overdue")


def _key(item: dict) -> str:
    """Changes when the item moves to another status or a new due point (after it was done)."""
    return f"{item['status']}|{item.get('due_date')}|{item.get('due_km')}"


def maintenance_notifications(items: list[dict], notified: dict[str, str]) -> tuple[list[dict], dict[str, str]]:
    """Items to announce, and the new ``schedule_id -> key`` memory.

    Each schedule is announced once when it becomes *soon*, and once more when it
    becomes *overdue*. Back to *ok* (done), it is forgotten, so the next cycle is
    announced again.
    """
    fire: list[dict] = []
    memory: dict[str, str] = {}
    for item in items:
        if item.get("status") not in NOTIFY_STATUSES:
            continue
        key = _key(item)
        memory[item["schedule_id"]] = key
        if notified.get(item["schedule_id"]) != key:
            fire.append(item)
    return fire, memory
