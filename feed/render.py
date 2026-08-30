"""Render the static site into site/.

The page is laid out as an "order of play": items grouped into days, each day a
continuous time spine with articles pinned to their publish time.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import (
    DISPLAY_TZ,
    RECENT_DAYS_OPEN,
    SITE_DIR,
    SPORT_LABELS,
    SPORTS,
    TEMPLATES_DIR,
)
from .models import Item

_TZ = ZoneInfo(DISPLAY_TZ)

# Betting/tips content — fine in the feed, but a poor "lead story" for a sport.
_TIPS = re.compile(r"\b(best bets?|predictions?|betting|\bodds\b|acca|value bets?|tips)\b", re.IGNORECASE)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _local(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ)


def group_by_day(items: list[Item]) -> list[dict]:
    """Bucket already-sorted (newest-first) items into local-date groups."""
    days: list[dict] = []
    for it in items:
        local = _local(it.published_at or it.fetched_at)
        key = local.date().isoformat()
        if not days or days[-1]["key"] != key:
            days.append(
                {
                    "key": key,
                    "weekday": local.strftime("%A"),
                    "date_label": f"{local.day} {local.strftime('%B')}",
                    "entries": [],
                }
            )
        days[-1]["entries"].append({"item": it, "time": local.strftime("%H:%M")})
    for day in days:
        day["count"] = len(day["entries"])
    return days


def render(items: list[Item], statuses: list[dict]) -> None:
    visible = [it for it in items if it.sports_ok]
    counts = {s: sum(1 for it in visible if it.sport == s) for s in SPORTS}
    now = datetime.now(timezone.utc)
    days = group_by_day(visible)

    # "The catch of the day" — one lead per sport: that discipline's newest item
    # from the most recent day that reads as a story (real summary, ~last 22h).
    # Sports with nothing fresh get no card. The picks are pulled out of the feed
    # list so they don't show twice.
    featured: list[dict] = []
    if days:
        for sport in SPORTS:
            for cand in days[0]["entries"]:
                it = cand["item"]
                if it.sport != sport:
                    continue
                age_h = (now - _local(it.published_at or it.fetched_at)
                         .astimezone(timezone.utc)).total_seconds() / 3600
                if (age_h <= 22 and it.summary_method in ("feed", "extract")
                        and len(it.summary) >= 110 and not _TIPS.search(it.title)):
                    featured.append(cand)
                    break
        if featured:
            picked = {id(c) for c in featured}
            kept = [e for e in days[0]["entries"] if id(e) not in picked]
            days[0]["count"] -= len(days[0]["entries"]) - len(kept)
            days[0]["entries"] = kept

    html = _env().get_template("index.html.j2").render(
        days=days,
        featured=featured,
        recent_open=RECENT_DAYS_OPEN,
        today_key=now.astimezone(_TZ).date().isoformat(),
        sports=SPORTS,
        sport_labels=SPORT_LABELS,
        counts=counts,
        statuses=sorted(statuses, key=lambda s: (s["ok"], s["name"])),
        broken=[s for s in statuses if not s["ok"]],
        generated_at=now.isoformat(),
        total=len(visible),
    )

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    (SITE_DIR / "data.json").write_text(
        json.dumps({"items": [it.to_dict() for it in visible]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
