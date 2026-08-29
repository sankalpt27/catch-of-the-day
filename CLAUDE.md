# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal, **zero-cost** sports news feed for **cricket, F1, football (soccer), and
tennis** — nothing else. A scheduled job pulls curated RSS feeds, tags each item by
sport, writes a short summary, and renders one static HTML page hosted on GitHub
Pages. No server, no database, no paid API. `DESIGN.md` is the authoritative spec and
roadmap; keep it in sync when scope changes.

**The $0 constraint is hard.** If a change would need a server, a hosted database, or
a paid API, stop and flag the cost before building — the whole architecture exists to
avoid it.

## Commands

Local dev needs **Python 3.13** (`/opt/homebrew/bin/python3`) — the system 3.8 lacks
TLS certs and feed fetches fail. A `.venv` is already set up.

```sh
.venv/bin/python -m feed build          # the whole pipeline → writes site/ and data/items.json
.venv/bin/python -m pytest -q            # all tests
.venv/bin/python -m pytest -k trim_to_sentence   # one test / pattern

# preview the built page
cd site && python3 -m http.server 8765   # then open http://localhost:8765/
```

Screenshotting the page with headless Chrome works down to ~560px wide; **below that,
headless ignores the viewport meta** and the capture is misleading — trust the CSS or
a real phone.

`rm data/items.json` before a build to start the rolling store from scratch (safe —
it's just a cache; you lose the local archive, CI rebuilds it).

## Architecture

One command, `python -m feed build` ([feed/build.py](feed/build.py)), runs a linear
pipeline:

1. **fetch** ([feed/fetch.py](feed/fetch.py)) — `httpx` does the HTTP (real TLS,
   redirects, conditional GET), `feedparser` parses. Raises `FeedError` on transport
   failure so the run continues and the source is marked broken.
2. **parse** ([feed/parse.py](feed/parse.py)) — feed entries → `Item`
   ([feed/models.py](feed/models.py), the one type that flows through everything and
   into `data/items.json`). **Item identity is the normalized article URL**, not the
   feed's `<guid>` — BBC lists one article under several sections with different
   guids but one link; `_normalize_url` also strips `utm_*`/`at_*` tracking params.
3. **sport tagging** ([feed/sport_tags.py](feed/sport_tags.py)) — sources with a real
   `sport:` in `sources.yaml` are trusted as-is; `sport: multi` sources are
   classified per-item by keyword rules. Items matching none of the four sports get
   `sports_ok=False` (kept in JSON, hidden from the page).
4. **summary** ([feed/summarize.py](feed/summarize.py)) — use the feed's own
   description when it's usable prose. `_strip_standfirst` removes Guardian-style
   bulleted / lead-`<p>` standfirsts ("Sign up for the Spin", "Get in touch: mail…").
   Thin/missing → returns `("", "stub")`.
5. **extractive fallback** ([feed/extract.py](feed/extract.py)) — for new, in-scope
   stubs only: fetch the article, `trafilatura` for the body, then the in-house
   frequency summarizer in [feed/textutil.py](feed/textutil.py) (`summarize_text` —
   no `sumy`/NLTK, deliberately, to avoid model downloads). Result is kept only if it
   reads as prose, else the item stays a stub. Capped at `EXTRACT_BUDGET` fetches/run.
6. **store** ([feed/store.py](feed/store.py)) — `data/items.json` is dedupe memory +
   summary cache + a `RETENTION_DAYS` rolling archive, committed back to the repo by
   CI. `merge` never mutates existing items (stable `fetched_at`, cached summary) and
   skips items already older than the cutoff (feeds carry months of history).
7. **render** ([feed/render.py](feed/render.py)) — groups items into local-date
   "days of play" (`DISPLAY_TZ`, currently Asia/Kolkata), then one Jinja template.

### The page ([feed/templates/index.html.j2](feed/templates/index.html.j2))

Single self-contained file — inline CSS and vanilla JS, no build step, no external JS.
Concept is "Order of Play": days on a continuous time spine, each item pinned to its
publish time, sport shown as a coloured lane on the spine. Floodlit-night palette with
a Day/Night toggle; Barlow Condensed / Fraunces / IBM Plex Mono (Google Fonts, the
only external resource). Progressive enhancement — readable with JS off; JS adds the
sport filter (persisted + URL-hash `#f1` for sharing), "new since last visit"
(localStorage), keyboard nav, the running clock, and the spine-draw animation.
`localStorage` keys are all `sportsfeed.*`.

When you change summary/tagging logic, existing `data/items.json` entries keep their
old values (merge doesn't re-process) — `rm data/items.json && python -m feed build`
to see the change across the whole feed.

## Deployment

`.github/workflows/build.yml` runs twice daily (cron, ~07:00 & 19:00 IST) + on pushes
touching `feed/` or `sources.yaml`: build → commit `data/items.json` → deploy `site/`
to Pages. `test.yml` runs pytest on PRs and pushes. First CI run after a deploy is
slow (fetches ~20 articles for the extractive pass), then the cache makes it fast.
One-time setup: repo **Settings → Pages → Source: GitHub Actions**, public repo.

## Sources

[`sources.yaml`](sources.yaml) — `key` (stable, don't rename), `name`, `feed_url`,
`site_url`, `sport` (`cricket`/`f1`/`football`/`tennis`/`multi`), `active`. Verify a
new feed with `curl` first; several "sport" feeds from big outlets are actually
all-sport feeds (this bit us with Sky Sports — check the article link paths, not the
feed `<title>`). Set `active: false` to pause without deleting.
