"""Feed fetching: httpx does the HTTP (proper TLS, redirects, conditional GET),
feedparser does the parsing."""
from __future__ import annotations

import feedparser
import httpx

from .config import USER_AGENT

_ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml;q=0.9, "
    "text/xml;q=0.8, */*;q=0.5"
)


class FeedError(Exception):
    pass


def fetch_feed(url: str, etag: str | None = None, modified: str | None = None):
    """Return a parsed feedparser dict.

    Adds `.status`, `.etag`, `.modified` to the result. Raises FeedError on
    transport/HTTP failures so the caller can record a clean status line.
    A 304 (not modified) comes back as an empty result with `.status == 304`.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": _ACCEPT}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified

    try:
        with httpx.Client(follow_redirects=True, timeout=25.0, headers=headers) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        raise FeedError(f"{type(exc).__name__}: {exc}") from exc

    if resp.status_code == 304:
        result = feedparser.util.FeedParserDict(entries=[], feed={}, bozo=False)
        result["status"] = 304
        return result

    if resp.status_code >= 400:
        raise FeedError(f"http {resp.status_code}")

    result = feedparser.parse(resp.content)
    result["status"] = resp.status_code
    result["etag"] = resp.headers.get("ETag")
    result["modified"] = resp.headers.get("Last-Modified")
    return result
