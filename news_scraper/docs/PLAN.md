# Plan — Hacker News Daily Scraper

> How to use this file: this is a **single living document**, edited in
> place — never date-versioned. When an item here is finished: if it was a
> durable decision, summarize it into `docs/DECISIONS.md`; the detailed
> narrative goes in `logs/YYYY-MM-DD.md`. Once captured elsewhere, remove
> the item from this file instead of leaving it to accumulate. This file
> should always read as "what's true right now," not a history.

## Current status

Production and stable. Two GitHub Actions workflows run on schedule:
`hn_top.yml` (twice daily) and `hn_weekly.yml` (weekly). The former daily
`hn_best.yml` workflow was retired on 2026-10-31; historical Best pages are
preserved. Each new day now has one Top Stories URL: the morning run publishes
exactly 50 items as `Morning 50`, and the evening run updates that same page to
exactly 100 items as `All 100`. Historical Daily Best and Trending pages are
left unchanged. Completed calendar months also receive a score-ranked Top 200
Best of the Month page, linked at the matching month boundary in the archive.
As of 2026-09-11: 204+ days of data, 30,000+ stories archived
under `hackernews/`.

## Current goal

Reduce recurring LLM cost while improving bilingual summary fidelity. Top runs
twice daily on one daily page, prior stories are reused across the full archive,
GPT tag classification is incremental, and new summaries use a
strictly bounded source excerpt: 2–3 factual sentences followed by at most one
source-supported significance sentence. New summaries use `gpt-5.6-luna`;
tagging remains on `gpt-5-nano` so the quality/cost change stays isolated.

## In progress

Nothing.

## Next steps

None currently planned. Candidate ideas mentioned in old notes
(`logs/archive/analysis_report.md`, `logs/archive/analysis_notes.md`) that
were never scheduled:
- Tag-based filtering UI on the index/search page (tags are already stored
  per-item; only the UI is missing).
- `onerror` fallback for external preview images (currently relies on CSS
  placeholder + lazy loading only).
- Search index growth is unbounded (grows ~100 items/day); no sharding plan
  exists yet.

## Known issues

- **`logs/openai_token_usage_log.md` is git-tracked and append-only.** It
  already has 10k+ lines. It is not currently rotated/archived — if this
  becomes a real problem, decide a rotation scheme (e.g. yearly file) and
  update `token_logger.py` + the two workflows' Job Summary `tail` commands
  together, since they hardcode this filename.
- **External preview images depend entirely on third-party sites staying
  up** — no local caching, no error fallback in the rendered HTML.

## Open questions

None currently.
