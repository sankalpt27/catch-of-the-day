"""Orchestrate one build: fetch every active source, merge, enrich, prune, render."""
from __future__ import annotations

from datetime import datetime, timezone

from .config import EXTRACT_BUDGET, load_sources
from .extract import article_summary
from .fetch import FeedError, fetch_feed
from .models import Item
from .parse import entries_to_items
from .render import render
from .store import load_items, merge, prune, save_items, sorted_items


def build() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    sources = [s for s in load_sources() if s.active]
    store = load_items()
    statuses: list[dict] = []
    added: list[Item] = []

    for src in sources:
        try:
            parsed = fetch_feed(src.feed_url)
        except FeedError as exc:
            statuses.append(_status(src, ok=False, detail=str(exc)[:140]))
            continue
        except Exception as exc:  # unexpected — keep the run going
            statuses.append(_status(src, ok=False, detail=f"{type(exc).__name__}: {exc}"[:140]))
            continue

        n_entries = len(parsed.entries)
        http_status = getattr(parsed, "status", None)

        if n_entries == 0:
            reason = "no entries"
            if getattr(parsed, "bozo", False):
                reason = f"parse error ({type(parsed.get('bozo_exception')).__name__})"
            elif http_status and http_status >= 400:
                reason = f"http {http_status}"
            statuses.append(_status(src, ok=False, detail=reason))
            continue

        fresh = merge(store, entries_to_items(src, parsed, now_iso))
        added.extend(fresh)
        statuses.append(
            _status(src, ok=True, detail=f"http {http_status or 200}",
                    entries=n_entries, new=len(fresh))
        )

    enriched = _fill_stub_summaries(added)

    store = prune(store)
    save_items(store)
    render(sorted_items(store), statuses)

    broken = [s["key"] for s in statuses if not s["ok"]]
    print(
        f"sources={len(sources)} new={len(added)} enriched={enriched} "
        f"total={len(store)} broken={broken or 'none'}"
    )


def _fill_stub_summaries(items: list[Item]) -> int:
    """Fetch article bodies for new, in-scope items that have no feed summary."""
    targets = [it for it in items if it.sports_ok and it.summary_method == "stub"]
    filled = 0
    for item in targets[:EXTRACT_BUDGET]:
        try:
            summary = article_summary(item.url, item.title)
        except Exception:
            summary = None
        if summary:
            item.summary = summary
            item.summary_method = "extract"
            filled += 1
    return filled


def _status(src, *, ok: bool, detail: str, entries: int = 0, new: int = 0) -> dict:
    return {
        "key": src.key,
        "name": src.name,
        "sport": src.sport,
        "ok": ok,
        "detail": detail,
        "entries": entries,
        "new": new,
    }
