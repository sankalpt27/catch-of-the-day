"""Render the static site into site/.

The page is laid out as an "order of play": items grouped into days, each day a
continuous time spine with articles pinned to their publish time.
"""
from __future__ import annotations

import json
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

    html = _env().get_template("index.html.j2").render(
        days=group_by_day(visible),
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
