"""Produce a short summary for an item from the feed's own text — no paid API.

If this returns a "stub", build.py's extractive pass tries to fill it from the
article body (feed/extract.py).
"""
from __future__ import annotations

import re

from .config import SUMMARY_MAX_CHARS, SUMMARY_MIN_CHARS
from .textutil import shorten, strip_html, tidy_summary, trim_to_sentence

# Guardian (and others) embed a standfirst in the feed description — bulleted
# "Get in touch: mail…" / "Sign up for the Spin" lists, or a lead <p> of nav
# links separated by " | ". None of it is article prose.
_LIST_BLOCK = re.compile(r"<(ul|ol)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_LEAD_P = re.compile(r"\s*<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_STANDFIRST_MARKERS = ("sign up", "get in touch", "mail ", "follow us on", "| mail")


def _strip_standfirst(raw: str) -> str:
    raw = _LIST_BLOCK.sub(" ", raw)
    match = _LEAD_P.match(raw)
    if match:
        lead = strip_html(match.group(1)).lower()
        rest = raw[match.end():]
        if any(m in lead for m in _STANDFIRST_MARKERS) and len(strip_html(rest)) >= 60:
            raw = rest
    return raw


def _raw_from_entry(entry) -> str:
    raw = ""
    if entry.get("summary"):
        raw = entry["summary"]
    else:
        content = entry.get("content")
        if content:
            try:
                raw = content[0].get("value", "")
            except (AttributeError, IndexError, TypeError):
                raw = ""

    trimmed = _strip_standfirst(raw)
    return trimmed if len(strip_html(trimmed)) >= 40 else raw


def summarize(entry, title: str) -> tuple[str, str]:
    """Return (summary, method) where method is 'feed' or 'stub'."""
    text = tidy_summary(strip_html(_raw_from_entry(entry)))

    if text and text.lower().strip(".") == title.lower().strip("."):
        return "", "stub"  # summary is just the headline again

    if len(text) < SUMMARY_MIN_CHARS:
        return "", "stub"  # too thin — let the extractive pass try

    summary = trim_to_sentence(shorten(text, SUMMARY_MAX_CHARS))
    return (summary, "feed") if len(summary) >= 40 else ("", "stub")
