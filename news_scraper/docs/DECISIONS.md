# Decisions — Hacker News Daily Scraper

Concise, durable record of *why*, not a changelog. Detailed narrative stays
in `logs/`; this file is the index into it.

---

**2026-10-31 — Add monthly Top 200 digests and simplify archive date labels.**
The archive's ISO week heading owns the year, so daily dates and week ranges use
numeric `MM-DD` labels instead of repeating `YYYY-MM-DD`. Each completed month
gets a Best of the Month page containing up to 200 unique stories, ranked by the
highest HN score observed during that month. The digest is assembled entirely
from existing daily JSON, so it incurs no LLM cost. Its archive card appears
immediately before the week containing the month's final day, which places it
visually at the boundary between months. See `logs/2026-10-31.md`.

**2026-10-31 — Future Top Stories use one daily URL with Morning 50 and All 100 editions.**
The morning Top run publishes exactly 50 unique stories and labels the page
`Daily Top Stories · Morning 50`. The evening run updates the same JSON, Markdown
page, and URL to exactly 100 unique stories labeled `Daily Top Stories · All
100`; it retains and refreshes the morning IDs, skips duplicates, and scans
farther down the current HN list until the target is met. Any story found in the
existing archive reuses its generated content and only refreshes HN metrics.
Historical Daily Best and Trending pages remain untouched and retain their old
labels. See `logs/2026-10-31.md`.

**2026-10-31 — Retired the scheduled Best feed, reduced Top to twice daily,
and made GPT tag classification incremental.**
Context: the pipeline's OpenAI prepaid balance was exhausted after recurring
spend of roughly $1.60–$1.78/month. The frequent Top feed is the useful live
surface; the slowly changing Best feed was no longer worth a separate daily
run. Historical Best JSON/Markdown and the manual `best` mode remain intact,
so existing URLs and weekly-digest inputs continue to work. Top now runs at
15:00 and 03:00 UTC (roughly morning/evening in America/Los_Angeles).
Previously, one newly merged untagged item caused `tag_json_file()` to send
the entire 50–100 item JSON back through the tag model. It now sends only
items whose `tags` field is missing/empty and preserves all existing tags;
`force=True` still performs a complete re-tag.

New-story summaries now use transient source context instead of title-only
inference. Extraction removes common page chrome/noise and uses page metadata
plus at most the first two substantial paragraphs rather than list items. It is
capped at 1,200 characters per story; HN self-post text takes priority. The
prompt requests 2–3 factual sentences and permits at most
one source-supported significance sentence, with fewer claims when a source is
blocked or sparse. See `logs/2026-10-31.md`.
Source fetch failures are expected and isolated per story: title-only items use
the previous concise fallback and remain in the batch. Downloads are capped at
512 KiB so malformed or unusually large pages cannot create unbounded memory or
bandwidth use.

Summary enrichment moved from deprecated `gpt-5-nano` to `gpt-5.6-luna`, the
cost-sensitive GPT-5.6 tier. Tag classification remains on `gpt-5-nano` during
the first evaluation so summary-quality and cost changes can be measured
independently. The token cost ledger includes Luna's official standard rates.

**2026-09-11 — This repo standardized as "Jekyll site + independent
news_scraper automation project," not restructured as a single generic project.**
Context: applying a general project-standardization template (used on other,
non-website projects) to this repo. `_layouts/`, `_includes/`, `_sass/`,
`_data/`, `_config.yml`, `assets/`, `hackernews/`, `deep-learning/` are
Jekyll-reserved names or live URL paths — renaming/moving them would break
the GitHub Pages build or change published URLs. `news_scraper/` is excluded
from the Jekyll build (`_config.yml` → `exclude:`), so it was standardized
in full (this docs/ folder, logs/archive/, etc.) while the site itself only
got documentation additions, no directory changes.
See `logs/2026-09-11.md`.

**2026-09-11 — Repo stays public; the plan's "always create a private
GitHub repo" default does not apply here.**
Context: `chaowang15.github.io` is a GitHub Pages *user site*, which requires
a public repository on a free GitHub plan. There was never a decision to
make here beyond confirming this is an intentional, permanent exception.

**2026-09-11 — `news_config.yml` stays at the repo root; not migrated to
`config/config.yaml`.**
Context: the standardization template prefers a single `config/config.yaml`.
`news_config.yml` is already a clean, secret-free YAML file, is the *only*
config file the pipeline reads (`main.py: load_config("news_config.yml")`,
hardcoded filename), and is already excluded from the Jekyll build. Moving
it would require touching `main.py` and adds no real benefit — it was left
as-is rather than migrated for its own sake.

**2026-09-11 — `logs/scrape_run_log.md` and `logs/openai_token_usage_log.md`
were left in place; other files under `logs/` were moved to `logs/archive/`.**
Context: those two files are hardcoded paths written by `run_logger.py` /
`token_logger.py` and historically read back by `hn_best.yml` / `hn_top.yml`'s
Job Summary step. After the 2026-10-31 retirement of `hn_best.yml`, only
`hn_top.yml` reads them. Moving them would require coordinated changes across
two Python modules and that workflow file for no benefit. Everything else in the old
`logs/` (`CHANGELOG.md`, `analysis_report.md`, `hn_api_research.md`,
`implementation_notes.md`, `integration_proposal.md`, etc.) was old ad hoc
session notes with no code/workflow references (confirmed by grep) and was
archived, not deleted.

**2026-09-11 — Documentation language split: `logs/*.md` and
`docs/DEVELOPMENT.md` are Chinese-primary (English keywords kept for
searchability); `README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`,
`docs/PLAN.md`, and this file stay English.**
Context: the user reads `logs/` and `DEVELOPMENT.md` directly and wants to
scan them quickly in Chinese; `CLAUDE.md`/`ARCHITECTURE.md`/`PLAN.md`/`DECISIONS.md`
are primarily read by an agent before doing work, so English is kept for
concision. `README.md` was left English rather than converted, since it's
already short and the user confirmed no change was needed there. This
mirrors the standardization template's own recommended split (§8 of
`Plan_Project_Standardization_Prompt_v2.md`).

**(pre-existing, date unknown) — API keys via GitHub Actions secrets, not a
config file or `.env`.**
Context: `OPENAI_API_KEY` is injected as an env var from
`secrets.OPENAI_API_KEY` in each of the three workflows and read implicitly
by the `openai` SDK. This already matches the standardization template's
"secrets live in env vars, never in repo files" rule — no migration needed.

**(pre-existing, date unknown, inferred from `logs/archive/hn_api_research.md`)
— Chose HN's `top` stories (not `best`) for the frequent/incremental feed,
kept `best` as the once-daily "hall of fame" feed.**
Context: research comparing the two HN endpoints found `top` has much higher
day-to-day turnover (list changes hourly, driven by a recency-weighted
ranking) while `best` changes slowly (~50% overlap day to day). A "daily
news digest" wants freshness, so `top` became the incremental/frequent mode
and `best` the once-daily curated mode — this is reflected in
`hn_top.yml` (every 4h) vs. `hn_best.yml` (once daily) and in `main.py`'s
mode-specific content-date logic.

**(pre-existing, date unknown, inferred from `logs/archive/summary_analysis.md`)
— LLM prompt changed to forbid boilerplate disclaimers and allow general-knowledge context.**
Context: early summaries frequently padded with lines like "the summary
uses only the title and URL context," adding no value. The prompt in
`llm_batch.py` was revised to explicitly forbid that pattern and instead ask
for *why the story matters*, with the Chinese summary written independently
rather than as a literal translation.

**(pre-existing, date unknown, inferred from `logs/archive/implementation_notes.md`)
— Added a tag system (GPT-classified categories) rather than manual tagging.**
Context: no HN API field carries a topic category. `tag_generator.py`
classifies each item into predefined categories via the tag LLM model
(`news_config.yml: llm.tag_model` / `tag_fallback_model`), stored per-item in
the JSON (`tags` field) and rendered as badges by `md_writer.py`. Since
2026-10-31 only missing tags are sent to the model; existing tags are reused.
This enabled the later tag-cloud and tag-trend pages.
