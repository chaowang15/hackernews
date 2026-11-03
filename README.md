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
