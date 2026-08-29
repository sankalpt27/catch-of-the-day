# Sports Feed — Design & Requirements

A personal, no-cost news feed for **cricket, F1, football (soccer), and tennis**:
newsletters, blogs, research, and individual writers pulled into one clean page to
read morning and evening.

Status: **pre-build**. This doc is the agreed frame before any code.

**Hard constraint: $0. No paid services, no credit card, no paid API.**

---

## 1. Scope

**v1 — "just aggregate"**
- Pull from a curated set of **RSS/Atom** sources.
- Cover four sports only: **cricket, F1, football (soccer), tennis**.
- One clean page, refreshed **twice a day** (morning + evening), items newest-first,
  filterable by sport.
- Title + short summary per item, built **without any paid API**.
- No login. No accounts. No server. No database.

**v2 — personal touches (client-side only, still $0)**
- "New since last visit" highlighting (browser `localStorage`).
- Notes + shortlist stored in the browser, with JSON export/import.
- Simple client-side re-ranking from thumbs up/down.

**Later / not now**
- Accounts + sync across devices (needs a backend → revisit cost then).
- HTML scrapers for feed-less sources; social (X / Reddit / YouTube).
- Live scores, transactions, full-text archive search.
- LLM summaries (only if a genuinely free tier is added — see §6).

**Non-goals (permanent)**
- Non-sports news. Real-time breaking news. This is a twice-a-day read.

---

## 2. Architecture — static site, built by cron

Nothing runs continuously. A scheduled GitHub Actions job builds an HTML page and
publishes it to free static hosting.

```
  GitHub repository (the whole project)
  │
  ├─ sources.yaml          curated feed list (name, url, sport, site)
  ├─ feed/ (Python pkg)     fetch → parse → dedupe → tag → summarize → render
  ├─ data/items.json        rolling ~30-day store, committed back by the job
  │                         (dedupe memory + archive + summary cache)
  ├─ templates/             Jinja2 → static HTML
  └─ .github/workflows/build.yml
         cron 2×/day  ──▶  run builder  ──▶  commit data/items.json
                                          └▶ deploy site/ to Pages

  GitHub Pages  ──▶  https://<user>.github.io/<repo>/   (free, static)
  Browser       ──▶  reads the page; localStorage holds per-device state (v2)
```

### Why this is free
| Piece | Service | Free? |
|---|---|---|
| Code + data + summary cache | GitHub repo | Yes |
| Scheduled build (2 runs/day ≈ 6 min/day) | GitHub Actions | Yes — unlimited for public repos; 2000 min/mo private |
| Page hosting | GitHub Pages | Yes for a **public** repo |
| Summaries | feed text + local extractive algorithm | Yes — runs on the Action, no API |
| Per-device state (v2) | browser `localStorage` | Yes |

Private-repo note: GitHub Pages needs a public repo (or paid Pro). Nothing secret
lives here — all feeds are public — so a **public repo is fine**. If you want it
private, deploy `site/` to **Cloudflare Pages** free tier instead (works from a
private repo); the builder is unchanged.

### The tradeoff you're accepting
No server means **no cross-device sync**. Notes/shortlist/read-state live in whichever
browser you used. For a single reader that's acceptable; JSON export/import is the
escape hatch. Adding real accounts later means adding a backend and re-opening the
cost question.

---

## 3. The build pipeline

Run on cron and locally (same code):

1. **Load** `sources.yaml` and `data/items.json` (existing items = dedupe + cache).
2. **Fetch** each feed with `httpx` (timeout, `User-Agent`, honor `ETag` /
   `Last-Modified`). Record per-source status.
3. **Parse** with `feedparser`. Per entry: `guid_hash = sha1(guid or url)`.
   Skip if already known.
4. **Tag sport**: keyword/entity rules (players, teams, competitions per sport) →
   `sport`. Fall back to the source's default sport. Drop items that match none of
   the four sports (kept in JSON, flagged `sports_ok=false`).
5. **Summarize** (see §4) — only for genuinely new items; cached forever after.
6. **Merge** new items into `items.json`; prune entries older than ~30 days that
   aren't shortlisted.
7. **Render** `templates/` → `site/index.html` (+ `site/data.json` for the JS).
8. Action **commits** `data/items.json` and **deploys** `site/`.

Cron (times are UTC — set to your timezone; IST example shown):
```
schedule:
  - cron: "30 1,13 * * *"   # ~07:00 and ~19:00 IST
```

---

## 4. Summaries — no paid API

Per new item, cheapest acceptable path wins:

1. **Feed's own summary** — take `entry.summary` / `entry.content`, strip HTML,
   collapse whitespace. Use it if it's prose, ~120–800 chars, not a bare
   "Read more…", and not just the title repeated. (`summary_method = "feed"`)
2. **Local extractive** — if the feed text is thin/missing: fetch the article,
   extract main text with `trafilatura`, then take a 2-sentence extract
   (`sumy` LexRank, or first sentences as a fallback). No API, runs on the Action.
   (`summary_method = "extract"`)
3. **Stub** — if the fetch fails (paywall / 403): show title + source only.
   (`summary_method = "stub"`)

Every summary is cached in `items.json` keyed by `guid_hash`; unchanged items are
never re-processed. Extraction cost is only runner CPU/bandwidth — free.

Optional future upgrade, still $0: **Google AI Studio (Gemini Flash)** has a free
tier with no credit card. Could slot in as a better summarizer for method 2. Not in
v1 — extractive is good enough to start and has no rate limits or account setup.

---

## 5. Data shape

`data/items.json` — a list of:
```
{
  "id": "<guid_hash>",
  "source": "<source key>",
  "sport": "cricket|f1|football|tennis",
  "sports_ok": true,
  "url": "...",
  "title": "...",
  "summary": "...",
  "summary_method": "feed|extract|stub",
  "author": "... | null",
  "published_at": "ISO-8601",
  "fetched_at": "ISO-8601",
  "tags": ["..."]
}
```

`sources.yaml` — a list of:
```
- key: the-cricket-monthly
  name: The Cricket Monthly
  feed_url: https://...
  site_url: https://...
  sport: cricket          # default sport for this source
  active: true
```

No per-user tables — there are no users in v1.

---

## 6. Ranking

v1: **newest-first within each sport**, page grouped/filterable by sport. That's it —
"just aggregate."

v2 (client-side, from `localStorage` thumbs): nudge a per-source and per-tag score in
the browser and reorder. Same transparent weighted-signal idea as before, but it runs
in JS on the reader's device, so it stays $0 and needs no backend. All weights start
at 0; feedback moves them in `[-1, 1]`; slow decay toward 0.

---

## 7. Tech choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Requested; best feed/parse ecosystem. |
| Feed parsing | `feedparser` | Handles RSS + Atom quirks. |
| HTTP | `httpx` | Timeouts, conditional GET. |
| Article extraction | `trafilatura` | Main-text extraction for the stub fallback. |
| Extractive summary | in-house frequency scorer (`feed/textutil.py`) | Local, no API, no NLP data downloads. |
| Templating | `Jinja2` | Static HTML generation. |
| Config | `sources.yaml` (`pyyaml`) | Human-editable source catalog. |
| Frontend | Plain HTML + a little vanilla JS | Works without JS; JS adds filter + "new since last visit". |
| Tests | `pytest` + saved feed fixtures | Ingestion + tagging are the risky logic. |
| Schedule + host | GitHub Actions + GitHub Pages | Free. |

No framework, no database, no bundler.

---

## 8. Build phases

- **P0 — Scaffold** ✅ — repo layout, `sources.yaml` (22 active feeds), builder CLI
  (`python -m feed build`), `build.yml` (cron + Pages deploy) and `test.yml`.
- **P1 — Ingest + render** ✅ — fetch (`httpx`) → parse (`feedparser`) → dedupe →
  sport-tag → `data/items.json` (30-day rolling store) → static page, newest-first,
  sport filter, "new since last visit", source-health footer. Feed-text summaries
  with caption/trailer tidying.
- **P2 — Better summaries** ✅ — `feed/extract.py` fetches the article for items with
  no usable feed text, runs `trafilatura` + an in-house frequency summarizer, and
  keeps the result only if it reads as prose (else the item stays a stub). Budget
  `EXTRACT_BUDGET` fetches/run. `strip_html` now spaces HTML block boundaries;
  `trim_to_sentence` drops feed-truncated fragments. Typical run: ~634 feed /
  ~16 extract / ~1 stub.
- **Frontend** ✅ — "Order of Play" design: day groups on a continuous time spine,
  sport shown as a coloured lane; floodlit-night palette + Day/Night toggle;
  Barlow Condensed / Fraunces / IBM Plex Mono; running session clock; older days
  fold away. See `feed/templates/index.html.j2` (single file, inline CSS/JS).
- **P3 — Reader polish** ✅ — keyboard nav (`j`/`k`/`o`/`g`/`G`/`t`/`1–5`/`?`),
  shareable URL-hash sport filter (`#f1`) with matching `<title>`, skip link,
  clickable "N new" jump. `summarize._strip_standfirst` drops Guardian bulleted
  and lead-`<p>` standfirsts ("Sign up for the Spin", "Mail Tanya", "Get in touch
  … BlueSky"). Fixed `skysports-football` (was pointed at Sky's all-sport feed →
  everything mis-tagged football; now `/rss/11095`, football-only).
- **P4 — Client-side notes/shortlist** — `localStorage`, JSON export/import.
- **P5 — Client-side re-ranking** — thumbs → in-browser weighted score.

Each phase is independently deployable.

### First-deploy checklist (do once)
1. `git init`, create a **public** GitHub repo, push.
2. Repo **Settings → Pages → Source: GitHub Actions**.
3. Run the `build-feed` workflow manually (Actions tab → Run workflow) to seed.
4. Confirm `https://<user>.github.io/<repo>/` loads.

---

## 9. Decisions locked (2026-08-29)

1. **Seed sources** — researched; see `sources.yaml` (23 feeds, all curl-verified).
   Owner prunes over time via the `active` flag.
2. **Repo**: **public** → GitHub Pages directly.
3. **Refresh**: twice daily, **~07:00 and ~19:00 IST** → cron `30 1,13 * * *` (UTC).
4. **Research papers**: skipped for v1.
5. **Layout**: one page, newest-first, with a sport filter (no separate per-sport
   pages in v1).

## 10. Still open

- Timezone is assumed **IST**; adjust the cron if wrong.
- `crictracker` and `the-analyst` are higher-volume / multi-sport — watch for noise
  after P1 and pause or down-rank if needed.
