# Sports Feed

A personal, zero-cost feed for **cricket, F1, football (soccer), and tennis**. A
scheduled job pulls a curated set of RSS feeds, tags each item by sport, writes a
short summary, and rebuilds one clean HTML page — hosted free on GitHub Pages.

See [DESIGN.md](DESIGN.md) for the full rationale and roadmap.

## Run it locally

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m feed build
open site/index.html          # macOS; or just open the file in a browser
```

`python -m feed build` does everything: fetch every active source in
`sources.yaml`, merge new items into `data/items.json` (dedupe + 30-day archive),
and render `site/`.

## Sources

Edit [`sources.yaml`](sources.yaml). Each entry needs `key`, `name`, `feed_url`,
`site_url`, `sport` (`cricket` / `f1` / `football` / `tennis` / `multi`). Set
`active: false` to pause a feed without deleting it. `multi` sources are
classified per-item by keyword rules in `feed/sport_tags.py`.

## How deployment works

`.github/workflows/build.yml` runs twice a day (~07:00 & ~19:00 IST), plus on any
push that touches `feed/` or `sources.yaml`. It builds the site, commits the
updated `data/items.json` back to the repo, and deploys `site/` to GitHub Pages.

**One-time setup:** repo **Settings → Pages → Build and deployment → Source:
GitHub Actions**.

## Layout

| Path | What |
|---|---|
| `feed/build.py` | orchestration — the `build` command |
| `feed/fetch.py` / `parse.py` | fetch feeds, turn entries into `Item`s |
| `feed/sport_tags.py` | keyword rules: sport classification + tags |
| `feed/summarize.py` | summary from the feed's own text |
| `feed/extract.py` | fallback: fetch the article, extract a 2-sentence summary |
| `feed/store.py` | load / merge / prune / save `data/items.json` |
| `feed/render.py` + `feed/templates/` | the static page |
| `data/items.json` | rolling store, committed by CI |
| `site/` | build output (git-ignored; deployed by CI) |
