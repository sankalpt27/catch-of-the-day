"""Extractive summary fallback: fetch the article, pull the body, pick 2 sentences.

Used only for items whose feed gave us no usable description. No paid API — runs
entirely on the build machine. Returns None (leaving the item a "stub") whenever
the result would be worse than an honest "open the report".
"""
from __future__ import annotations

import re

import httpx

from .config import SUMMARY_MAX_CHARS, USER_AGENT
from .textutil import shorten, summarize_text, tidy_summary, trim_to_sentence

_MIN_BODY = 240
_SENTENCES = 2
_WORDS = re.compile(r"[a-z']+")
_LOOKS_LIKE_SENTENCE = re.compile(r"[.!?][\"'’)\]]?$")
BOILERPLATE = re.compile(
    r"\bcookies?\b(?=.*\b(?:allow|enable|accept|preferences|technolog|consent|session)\b)"
    r"|allow cookies|enable cookies|accept (?:all )?cookies|cookie preferences"
    r"|we need your permission|to (?:show|view) (?:you )?this content|content is provided by"
    r"|subscribe to (?:read|continue)|sign in to (?:read|continue|your)"
    r"|create an account|javascript is (?:disabled|required)|please enable javascript",
    re.IGNORECASE | re.DOTALL,
)


def _fetch_body(url: str) -> str | None:
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code >= 400 or not resp.text:
        return None

    # Lazy import — trafilatura pulls lxml and is only needed on the stub path.
    import trafilatura

    return trafilatura.extract(
        resp.text, include_comments=False, include_tables=False
    ) or None


def _prose_only(body: str) -> str:
    """Keep lines that read as prose; drop headings, breadcrumbs, table rows."""
    kept = []
    for line in body.splitlines():
        line = line.strip().lstrip("#>-*•· ").strip()
        if len(line) < 45:
            continue
        if ". " not in line and not _LOOKS_LIKE_SENTENCE.search(line):
            continue
        if BOILERPLATE.search(line):
            continue
        kept.append(line)
    return " ".join(kept)


def _too_similar_to_title(summary: str, title: str) -> bool:
    title_words = set(_WORDS.findall(title.lower()))
    if not title_words:
        return False
    summary_words = set(_WORDS.findall(summary.lower()))
    overlap = len(summary_words & title_words) / len(title_words)
    return overlap > 0.8 and len(summary_words) <= len(title_words) + 5


def article_summary(url: str, title: str = "") -> str | None:
    body = _fetch_body(url)
    if not body:
        return None
    body = _prose_only(body)
    if len(body) < _MIN_BODY:
        return None

    summary = trim_to_sentence(
        shorten(tidy_summary(summarize_text(body, _SENTENCES)), SUMMARY_MAX_CHARS)
    )

    if len(summary) < 60:
        return None
    if not _LOOKS_LIKE_SENTENCE.search(summary) and ". " not in summary:
        return None
    if BOILERPLATE.search(summary) or _too_similar_to_title(summary, title):
        return None
    return summary
