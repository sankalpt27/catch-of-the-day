"""Turn a parsed feedparser result into Item objects."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from time import mktime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import SPORTS, Source
from .models import Item
from .sport_tags import classify, extract_tags
from .summarize import summarize


def _iso(struct_time) -> str | None:
    if not struct_time:
        return None
    try:
        return datetime.fromtimestamp(mktime(struct_time), tz=timezone.utc).isoformat()
    except (OverflowError, ValueError, TypeError):
        return None


def _normalize_url(url: str) -> str:
    """Drop the fragment and tracking params so a link is a stable identity.

    BBC (and others) append rotating ?at_medium=RSS&at_campaign=... params, which
    would otherwise make the same article look new on every fetch.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(("utm_", "at_"))
        and k.lower() not in {"cmp", "ito", "ns_campaign", "ns_mchannel"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def _item_id(entry) -> str:
    # Key on the normalized article URL, not the feed's <guid>: BBC (and others)
    # list one article under several sections, each with a different guid but the
    # same link. URL identity collapses those; the rare feed that puts genuinely
    # different items at one URL (a podcast strand) loses the extras, which is fine.
    link = entry.get("link")
    basis = _normalize_url(link) if link else (entry.get("id") or entry.get("title", ""))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _clean_author(entry) -> str | None:
    author = entry.get("author")
    if not author or not isinstance(author, str):
        return None
    author = author.strip()
    if author.lower().startswith("by "):
        author = author[3:].strip()
    return author or None


def entries_to_items(source: Source, parsed, now_iso: str) -> list[Item]:
    items: list[Item] = []
    for entry in parsed.entries:
        url = entry.get("link")
        title = (entry.get("title") or "").strip()
        if not url or not title:
            continue

        summary, method = summarize(entry, title)
        blob = f"{title}. {summary}"

        # Some feeds ship no date at all — fall back to first-seen time so the item
        # ages normally instead of floating at the top forever.
        published_at = _iso(
            entry.get("published_parsed") or entry.get("updated_parsed")
        ) or now_iso

        if source.sport == "multi":
            sport, ok = classify(blob, default="")
        else:
            sport, ok = source.sport, True

        in_scope = ok and sport in SPORTS
        items.append(
            Item(
                id=_item_id(entry),
                source=source.key,
                source_name=source.name,
                sport=sport if sport in SPORTS else "other",
                sports_ok=in_scope,
                url=url,
                title=title,
                summary=summary,
                summary_method=method,
                author=_clean_author(entry),
                published_at=published_at,
                fetched_at=now_iso,
                tags=extract_tags(blob),
            )
        )
    return items
