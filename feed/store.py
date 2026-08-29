"""Load / merge / prune / save the rolling item store (data/items.json).

The store is dedupe memory + summary cache + a ~30-day archive. It is committed
back to the repo by the GitHub Actions job.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .config import DATA_FILE, RETENTION_DAYS
from .models import Item


def _parse_when(stamp: str | None) -> datetime:
    if not stamp:
        return datetime.now(timezone.utc)
    try:
        when = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _sort_key(item: Item) -> str:
    return item.published_at or item.fetched_at


def load_items() -> dict[str, Item]:
    if not DATA_FILE.exists():
        return {}
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {d["id"]: Item.from_dict(d) for d in raw.get("items", [])}


def retention_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def merge(
    existing: dict[str, Item], fresh: list[Item], cutoff: datetime | None = None
) -> list[Item]:
    """Add genuinely new items. Existing items are left untouched (stable
    fetched_at, cached summary). Items already older than the retention cutoff are
    skipped — feeds routinely carry months of history that we'd only prune again.
    Returns the items actually added (same objects now held in `existing`)."""
    cutoff = cutoff or retention_cutoff()
    added: list[Item] = []
    for item in fresh:
        if item.id in existing:
            continue
        if _parse_when(item.published_at or item.fetched_at) < cutoff:
            continue
        existing[item.id] = item
        added.append(item)
    return added


def prune(items: dict[str, Item]) -> dict[str, Item]:
    cutoff = retention_cutoff()
    return {
        k: it
        for k, it in items.items()
        if _parse_when(it.published_at or it.fetched_at) >= cutoff
    }


def sorted_items(items: dict[str, Item]) -> list[Item]:
    return sorted(items.values(), key=_sort_key, reverse=True)


def save_items(items: dict[str, Item]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted_items(items)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(ordered),
        "items": [it.to_dict() for it in ordered],
    }
    DATA_FILE.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
