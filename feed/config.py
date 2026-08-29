"""Paths, constants and the source catalog loader."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.yaml"
DATA_FILE = ROOT / "data" / "items.json"
SITE_DIR = ROOT / "site"
TEMPLATES_DIR = ROOT / "feed" / "templates"

# A browser-ish UA — several feeds (BBC, some WordPress) 403 the default urllib one.
USER_AGENT = "Mozilla/5.0 (compatible; SportsFeedBot/0.1; +https://github.com/)"

RETENTION_DAYS = 30
SUMMARY_MAX_CHARS = 500
SUMMARY_MIN_CHARS = 55  # shorter feed blurbs than this go to the extractive pass
# Cap on article fetches per build for the extractive summary pass.
EXTRACT_BUDGET = 60

# Timezone the page reads in — day headers and item times are shown in this zone.
DISPLAY_TZ = "Asia/Kolkata"
# Days of play shown expanded; older days fold behind a toggle.
RECENT_DAYS_OPEN = 3

SPORTS = ("cricket", "f1", "football", "tennis")
SPORT_LABELS = {"cricket": "Cricket", "f1": "F1", "football": "Football", "tennis": "Tennis"}


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    feed_url: str
    site_url: str
    sport: str  # one of SPORTS, or "multi"
    active: bool = True
    notes: str = ""


def load_sources() -> list[Source]:
    raw = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    sources: list[Source] = []
    for entry in raw["sources"]:
        sources.append(
            Source(
                key=entry["key"],
                name=entry["name"],
                feed_url=entry["feed_url"],
                site_url=entry.get("site_url", ""),
                sport=entry["sport"],
                active=entry.get("active", True),
                notes=entry.get("notes", ""),
            )
        )
    return sources
