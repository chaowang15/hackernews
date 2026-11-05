# Hacker News Daily

Static Daily, Weekly, and Monthly Hacker News digests published at
<https://chaowang15.github.io/hackernews/>.

## Workflows

All four run automatically; manual runs are optional.

| Workflow | Schedule | What it does |
|----------|----------|--------------|
| HN Top Stories (Incremental) | 8:05 and 18:05 America/Los_Angeles (four UTC triggers; a gate step picks the edition or skips) | Fetch top stories; `morning` = Morning 50, `full` = All 100 |
| HN Weekly Digest | Monday 09:00 UTC | Top 100 of the previous ISO week |
| HN Monthly Digest | 1st of the month 10:00 UTC | Top 200 of the previous month |
| Build and Deploy Pages | after each scraper workflow succeeds, and on pushes that touch the site | Jekyll build and GitHub Pages deploy (manual run builds only unless `publish` is checked) |

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
| Site pages, rolling past 7 / past 30 days (excluding today, ranked like the digests), trends, search shards | — | none (`site_v2.py` reads JSON) |

Each day's JSON `meta` records `reused_*` and `new_llm_enriched` counts; token usage is appended
to `logs/openai_token_usage_log.md`.

## Site front end (Neon Glass)

- `news_scraper/site_v2.py` renders the home page, Daily / Weekly / Monthly readers, rolling
  past-7 and past-30-day pages (excluding today, ranked by highest HN score like the digests), Trends, Favorites and Search from the JSON backups. It runs at the end of
  `update_hackernews_index()`, so every scheduled job refreshes all pages; URLs are unchanged.
- Layout `_layouts/hn2.html`; assets `assets/hn/v2/` (`base.css`, `theme.css`, `hn2.js`).
- Home "Top stories": Today / past 7 days / past 30 days (both windows exclude today and rank by
  highest HN score like the digests). Slots keep strict rank order; a story without a real image uses
  a text layout. "Real image" is decided from the URL only (no download, no LLM): expired signed URLs,
  GitHub repo cards, avatars, logo/favicon/icon file names or directories, SVGs, and images shared by
  3+ stories are treated as missing.
- Stories linking to GitHub (incl. gists), GitLab, Hugging Face, Codeberg, sourcehut, Bitbucket or Gitee get a
  derived `Code` tag (URL rule, no LLM). The home page has an "Open source this week" section (top 12 of the
  past 7 days). Every reader page (daily / weekly / monthly / past 7 or 30 days) has an All / Code switch
  (`?only=code`, remembered for the browser session); `code/` redirects to `top/30d?only=code`.
- The "Today" nav item opens the latest day page (the logo opens the home page); reader pages
  default to the titles-only view; weekly / monthly index cards list each digest's top five titles.
- Card and full views have a share button next to the favorite star: native share sheet on touch devices,
  clipboard (title + one-line summary + link) elsewhere. Links use the existing `share/<id>.html` pages
  (Open Graph preview, redirect to the day page anchor).
- Search data is sharded by month under `hackernews/search/`; Favorites use the existing
  `hnFavoritesV1` localStorage key.
- Local preview without Jekyll: `python news_scraper/site_v2.py --preview /tmp/hnprev`, then
  `python -m http.server -d /tmp/hnprev`.
- Share pages still use the legacy `_layouts/hn.html` and `assets/hn/hn.css`.
