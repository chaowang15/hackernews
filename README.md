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
