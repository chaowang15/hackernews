# Architecture — Hacker News Daily Scraper

`news_scraper/` is a Python automation pipeline that turns the Hacker News
API into static pages under `/hackernews/` on the Jekyll site. It runs
entirely inside GitHub Actions; there is no server or database.

## Data flow

```
GitHub Actions (cron)
    │
    ▼
news_scraper/main.py <best|top|all|rebuild>
    │
    ├─ hn_api.py         → HN Firebase API: story IDs + item details
    ├─ (dedup logic in main.py, see below)
    ├─ llm_batch.py       → OpenAI API: bilingual title/summary per new item
    ├─ image_fetcher.py   → preview image + bounded source excerpt from article URL
    ├─ tag_generator.py   → OpenAI API: category tags per item
    ├─ backup_io.py       → write/read the per-day JSON (source of truth)
    ├─ md_writer.py       → render the day's items into a Jekyll .md page
    ├─ index_updater.py   → rebuild hackernews/index.md
    ├─ search_index_builder.py → hackernews/search_index.json
    ├─ tag_cloud_builder.py    → hackernews/tag_cloud.json
    ├─ tag_trend_builder.py    → hackernews/tag_trend.json
    ├─ rss_builder.py          → hackernews/feed.xml
    ├─ share_page_builder.py   → OG-preview share pages
    ├─ run_logger.py      → append to logs/scrape_run_log.md
    └─ token_logger.py    → append to logs/openai_token_usage_log.md
    │
    ▼
Jekyll build (GitHub Pages) renders the generated .md files as HTML
```

`weekly_digest.py` and `resummarize.py` are separate entry points invoked
directly by their own workflows/manually; they reuse `llm_batch.py`,
`backup_io.py`, etc. but are not called from `main.py`.

`monthly_digest.py` aggregates each completed calendar month, deduplicates by
HN ID while retaining the highest observed score, and publishes at most the top
200 stories under `hackernews/monthly/YYYY-MM`. `hn_monthly.yml` runs on the
first day of each month. Monthly generation uses existing JSON only and makes no
LLM calls. Weekly and monthly compact cards also reuse the preview `image_url`
already stored in daily JSON; they never refetch article pages. Images are lazy
loaded. Daily, weekly, and monthly story cards share the same interaction and
compact styling: details are expanded by default, while clicking the
title/score surface collapses or reopens the stored bilingual summaries and
preview image. The details area does not toggle the card. Digest headline links
go directly to the original article rather than through the daily page.
Weekly and monthly headers also reuse each story's saved `created_display`, so
their timestamp row matches Daily cards without any new fetch or model call.

Favorites are entirely client-side. `assets/hn/hn.js` stores a compact copy of
the selected card in the versioned `hnFavoritesV1` browser `localStorage` key
and renders it at `/hackernews/favorites/`. There is no account, database,
network write, or cross-browser/device synchronization.

## Per-day JSON as source of truth

Every scrape writes `hackernews/YYYY/MM/DD/<prefix>_MMDDYYYY.json` — this is
the only place item data (HN metadata, LLM summaries, image URL, tags) is
persisted. The `.md` page for that day is always *rendered from* this JSON,
never edited directly. This is why `main.py rebuild` can regenerate every
historical `.md` page from JSON alone, with no HN API or LLM calls — it's
the standard way to roll out a template/CSS change retroactively.

## Modes (`main.py <mode>`)

| Mode      | Runs                                   | Content date        | Cap |
|-----------|-----------------------------------------|----------------------|-----|
| `best`    | manual only; scheduled workflow retired | previous day (UTC content date = run day − 1) | 50 |
| `top morning` | morning (`hn_top.yml`)             | current day          | exactly 50 |
| `top full` | evening (`hn_top.yml`); default for manual runs | current day | exactly 100 |
| `all`     | both sequentially                       | —                    | —  |
| `rebuild` | manual, no API/LLM calls                | —                    | —  |

## Deduplication (in `main.py`, `run_scrape`)

Because `top` runs incrementally and historical `best`/`top` data overlap
heavily, every fetched story is checked against four prior sources before
an LLM call is made, in priority order:

1. **Same-day** — today's own JSON (an earlier run today already summarized it).
2. **Cross-day** — yesterday's JSON for the same mode (title-similarity match).
3. **Cross-mode** — the other mode's JSON for the overlapping date (`best`
   also checks today's `top` JSON; `top` also checks yesterday's `best` JSON).
4. **Full archive** — the existing search index locates any older page with
   the same HN ID; its JSON is loaded lazily and reused after the same title
   and summary checks.

A match requires `_is_same_story()` (exact title match, substring match, or
>80% word overlap) *and* a non-empty prior summary. Matched items reuse the
LLM summary/title/image/tags and only get their `score`/`descendants`
refreshed from the API. Only genuinely new items go through bounded source
extraction and `llm_enrich_batch()`. The source excerpt contains page metadata
plus at most the first two substantial paragraphs, is transient, never
persisted, and is capped at 1,200 characters; HN self-post text takes priority.
Fetch errors, timeouts, blocked pages, non-HTML responses, and empty extraction
are isolated per item and fall back to title-only enrichment. HTML downloads
are capped at 512 KiB before parsing, so an abnormal page cannot grow without
bound or abort the whole scrape.
This is the main
cost-control mechanism — see `docs/DECISIONS.md`.

After the merged JSON is written, `tag_json_file()` sends only items with a
missing/empty `tags` field to the tag model. Existing items retain their
stored GPT tags and only receive the local keyword-supplement pass. Passing
`force=True` remains the explicit way to re-tag every item in a file.

For a new day, the morning run walks HN's ranked list until it has exactly 50
valid unique IDs. The evening run refreshes those same 50 IDs first, then walks
the current HN list past duplicates until the same JSON/page contains exactly
100 unique IDs. The URL never changes between editions. A short or malformed
API result aborts before the JSON is overwritten, rather than publishing a page
whose label overstates its count. The list is then ordered with a HN-style
`hot_score` —
`(score - 1) / (age_hours + 2)^1.8` — is computed and used as the default
sort order in both the JSON and the rendered page.

`index_updater.py` renders every available day into the News Archive, grouped
by ISO week. Daily labels omit the redundant year (`10-31`); the surrounding
week heading retains it (`2026 Week 44`). Completed monthly digests appear as
standalone Best of the Month cards at calendar-month boundaries. Historical
daily pages are not truncated from homepage navigation.

## External services

| Service | Used by | Auth |
|---|---|---|
| Hacker News Firebase API (`hacker-news.firebaseio.com`) | `hn_api.py` | none (public) |
| OpenAI API | `llm_batch.py`, `tag_generator.py` | `OPENAI_API_KEY` env var, injected from `secrets.OPENAI_API_KEY` in each workflow |
| Article origin sites (arbitrary) | `image_fetcher.py` | none — best-effort preview image and bounded paragraph extraction |

Models are configured in `news_config.yml` (`llm.model`, `llm.fallback_model`,
`llm.tag_model`, `llm.tag_fallback_model`), not hard-coded in the scripts.

## Configuration

- `news_config.yml` (repo root) — timezone, output dir, per-mode item counts,
  LLM model names, image-fetch settings. Loaded once in `main.py:load_config()`.
  Excluded from the Jekyll build via `_config.yml`'s `exclude:` list.
- `.github/workflows/hn_top.yml`, `hn_weekly.yml` — cron
  schedules, Python setup, `OPENAI_API_KEY` injection, and the
  commit-and-push step that publishes generated pages back to `main`.

## Logs (production, not dev-session logs)

Two files under the repo-root `logs/` are written by the pipeline on every
run and are read back by the workflows' Job Summary step — **do not move or
rename them** without updating `run_logger.py`, `token_logger.py`, and the
`hn_top.yml` Job Summary:

- `logs/scrape_run_log.md` — one line per run (mode, trigger, duration, item counts, tokens/cost).
- `logs/openai_token_usage_log.md` — per-batch LLM token/cost ledger.

Everything else that was previously in `logs/` (ad hoc analysis notes,
changelogs) has been moved to `logs/archive/` — see `docs/DECISIONS.md`.

## Front-end (not part of this Python pipeline, but consumed by it)

`assets/hn/hn.css` and `assets/hn/hn.js` implement the page's dark mode,
lazy image loading, lightbox, search UI, and tag filtering. `_layouts/hn.html`
is the Jekyll layout every generated `.md` page uses. `md_writer.py` renders
HTML that assumes these CSS classes/JS hooks exist — changing one without
the other will silently break rendering.
