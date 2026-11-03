# Hacker News Daily

Static Daily, Weekly, and Monthly Hacker News digests published at
<https://chaowang15.github.io/hackernews/>.

## Migration state

This repository was split from `chaowang15/chaowang15.github.io`. During the
staging phase:

- scraper workflows are manual-only;
- the Pages workflow builds without publishing unless `publish=true` is chosen;
- the existing site remains the production source.

Enable schedules and automatic Pages deployment only during the final cutover.

## Local paths

- Generated site source: `hackernews/`
- Scraper and digest builders: `news_scraper/`
- Shared frontend: `assets/hn/`
- Jekyll layout: `_layouts/hn.html`
- Pipeline configuration: `news_config.yml`

## What each run fetches

| Step | Network | LLM |
|------|---------|-----|
| Story list + per-story score/comments (HN API) | every run | — |
| Source page (article context, preview image) | new stories only | — |
| Chinese title, summaries | new stories only | yes |
| Tags | stories without tags only | yes |
| Reused stories (same day, previous day, other mode, history) | score/comments refreshed | none |
| Weekly / monthly digests | — | none (rank existing JSON) |
| Site pages, rolling 7/30 days, trends, search shards | — | none (`site_v2.py` reads JSON) |

Each day's JSON `meta` records `reused_*` and `new_llm_enriched` counts; token usage is appended
to `logs/openai_token_usage_log.md`.

## Site front end (Neon Glass)

- `news_scraper/site_v2.py` renders the home page, Daily / Weekly / Monthly readers, rolling
  7- and 30-day pages, Trends, Favorites and Search from the JSON backups. It runs at the end of
  `update_hackernews_index()`, so every scheduled job refreshes all pages; URLs are unchanged.
- Layout `_layouts/hn2.html`; assets `assets/hn/v2/` (`base.css`, `theme.css`, `hn2.js`).
- Search data is sharded by month under `hackernews/search/`; Favorites use the existing
  `hnFavoritesV1` localStorage key.
- Local preview without Jekyll: `python news_scraper/site_v2.py --preview /tmp/hnprev`, then
  `python -m http.server -d /tmp/hnprev`.
- Share pages still use the legacy `_layouts/hn.html` and `assets/hn/hn.css`.
