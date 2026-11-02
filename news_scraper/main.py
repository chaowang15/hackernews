"""
Hacker News Daily Scraper — main pipeline

Modes:
  best    — Fetch & enrich today's best stories (once daily, incremental with dedup)
  top     — Fetch & enrich today's top stories (incremental, multiple times daily)
  all     — Run both best and top sequentially
  rebuild — Rebuild all MD pages from existing JSON backups (no API, no LLM)

Features:
- Unified incremental dedup: both best and top modes use same-day + cross-day + cross-mode dedup
- Same-day deduplication: reuse LLM summaries from today's existing JSON, update scores
- Cross-day deduplication: reuse LLM summaries from previous day's JSON for overlapping stories
- Cross-mode deduplication: best mode also checks today's top JSON; top mode also checks yesterday's best JSON
- Score refresh: all reused items get fresh score/descendants from API on every scrape
- Per-mode item cap: best=50, top=100 (keep highest-scored after merging)
- Comprehensive logging for GitHub Actions debugging
- Fallback model support for both enrichment and tag generation
- Content cleaning and robust JSON parsing
"""

import glob
import html
import json
import os
import sys
import time
import yaml
from datetime import datetime, timezone, timedelta
from dateutil import tz
from typing import Optional
import re

from hn_api import get_story_ids, get_item, get_item_url
from llm_batch import llm_enrich_batch
from image_fetcher import fetch_page_context
from md_writer import render_markdown
from index_updater import update_hackernews_index
from search_index_builder import build_search_index
from tag_cloud_builder import build_tag_cloud
from tag_trend_builder import build_tag_trend
from token_logger import log_daily_summary, reset_session_stats, get_session_stats
from run_logger import log_scrape_run
from rss_builder import build_rss_feed
from share_page_builder import build_share_pages
from backup_io import write_backup_json, read_backup_json
from tag_generator import tag_json_file


TOP_STORIES_MAX = 100  # Maximum number of top stories to keep per day
BEST_STORIES_MAX = 50   # Maximum number of best stories to keep per day


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(tz.gettz(tz_name))


def fmt(dt: datetime, fmt_str: str) -> str:
    return dt.strftime(fmt_str)


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _ordered_unique_ids(existing_ids, current_ids):
    """Refresh today's IDs first, then append current HN IDs without repeats."""
    seen = set()
    ordered = []
    for value in list(existing_ids) + list(current_ids):
        story_id = int(value)
        if story_id in seen:
            continue
        seen.add(story_id)
        ordered.append(story_id)
    return ordered


def mmddyyyy(dt: datetime) -> str:
    return dt.strftime("%m%d%Y")


def _clean_hn_markdown(md: str) -> str:
    """
    Clean generated markdown for Jekyll layout=hn:
    - Remove injected <link> (fonts/css) and <script> tags that appear in BODY
    - Remove outer <div class='hn-wrap'> ... </div> wrapper (layout already provides it)
    """
    lines = md.splitlines()

    # 1) Preserve YAML front matter block if present
    start = 0
    fm_end = -1
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break

    out = []
    if fm_end != -1:
        out.extend(lines[: fm_end + 1])
        start = fm_end + 1

    # 2) Drop link/script tags right after front matter
    drop_patterns = [
        r"^<link\s+rel=['\"]preconnect['\"].*>$",
        r"^<link\s+href=['\"]https://fonts\.googleapis\.com/.*</link>$",
        r"^<link\s+href=['\"]https://fonts\.googleapis\.com/.*>$",
        r"^<link\s+rel=['\"]stylesheet['\"]\s+href=['\"]/assets/hn/hn\.css.*>$",
        r"^<script\s+src=['\"]/assets/hn/hn\.js.*</script>$",
        r"^<script\s+src=['\"]/assets/hn/hn\.js.*>\s*$",
    ]
    drop_re = [re.compile(p) for p in drop_patterns]

    i = start
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    while i < len(lines):
        s = lines[i].strip()
        if s == "":
            i += 1
            continue
        matched = any(r.match(s) for r in drop_re)
        if not matched and s.startswith("<link") and "fonts.gstatic.com" in s:
            matched = True
        if matched:
            i += 1
            continue
        break

    body_lines = lines[i:]

    # 3) Remove outer hn-wrap wrapper if it is the first non-empty body line
    j = 0
    while j < len(body_lines) and body_lines[j].strip() == "":
        j += 1

    if j < len(body_lines) and body_lines[j].strip() in ("<div class='hn-wrap'>", '<div class="hn-wrap">'):
        body_lines = body_lines[:j] + body_lines[j + 1 :]

        k = len(body_lines) - 1
        while k >= 0 and body_lines[k].strip() == "":
            k -= 1
        if k >= 0 and body_lines[k].strip() == "</div>":
            body_lines = body_lines[:k] + body_lines[k + 1 :]

    out.extend(body_lines)
    return "\n".join(out).rstrip() + "\n"


# ============================================================
# Cross-day deduplication: load previous day's JSON to reuse
# LLM summaries for overlapping stories
# ============================================================

def _load_previous_day_items(base_dir: str, content_dt: datetime, mode: str) -> dict:
    """
    Load the previous day's JSON file for the given mode (best/top).
    Returns a dict mapping hn_id -> item dict for quick lookup.
    """
    prev_dt = content_dt - timedelta(days=1)
    prefix_map = {"best": "best_stories", "top": "top_stories"}
    prefix = prefix_map.get(mode, f"{mode}_stories")

    date_dir = prev_dt.strftime("%Y/%m/%d")
    json_name = f"{prefix}_{prev_dt.strftime('%m%d%Y')}.json"
    json_path = os.path.join(base_dir, date_dir, json_name)

    if not os.path.exists(json_path):
        print(f"[DEDUP] No previous day JSON found: {json_path}")
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) or []
        prev_map = {}
        for item in items:
            hn = item.get("hn", {})
            hn_id = hn.get("id")
            if hn_id:
                prev_map[int(hn_id)] = item
        print(f"[DEDUP] Loaded {len(prev_map)} items from previous day: {json_path}")
        return prev_map
    except Exception as e:
        print(f"[DEDUP][WARN] Failed to load previous day JSON: {e}")
        return {}


def _load_cross_mode_items(base_dir: str, run_dt: datetime, content_dt: datetime, mode: str) -> dict:
    """
    Load items from the *other* mode's JSON for cross-mode deduplication.
    - For 'best' mode: load today's (run_dt) top_stories JSON
      (since best records yesterday's date but top records today's date,
       and they share many overlapping stories)
    - For 'top' mode: load content_dt's best_stories JSON
      (best stories for the same content date)
    Returns a dict mapping hn_id -> item dict.
    """
    cross_map = {}

    if mode == "best":
        # Best runs today but records yesterday's date.
        # Today's top_stories JSON uses today's date (run_dt).
        target_dt = run_dt
        prefix = "top_stories"
    elif mode == "top":
        # Top runs today and records today's date.
        # Today's best_stories JSON uses yesterday's date (content_dt - 0 for top = today,
        # but best for today records yesterday => we look at best for content_dt).
        # Actually: best that ran today records (today-1) as content_date.
        # So if top content_dt = today, best content_dt = today-1 = yesterday.
        # The best JSON for yesterday is at yesterday's date dir.
        target_dt = content_dt - timedelta(days=1)
        prefix = "best_stories"
    else:
        return cross_map

    date_dir = target_dt.strftime("%Y/%m/%d")
    json_name = f"{prefix}_{target_dt.strftime('%m%d%Y')}.json"
    json_path = os.path.join(base_dir, date_dir, json_name)

    if not os.path.exists(json_path):
        print(f"[CROSS-MODE] No cross-mode JSON found: {json_path}")
        return cross_map

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) or []
        for item in items:
            hn = item.get("hn", {})
            hn_id = hn.get("id")
            if hn_id:
                cross_map[int(hn_id)] = item
        print(f"[CROSS-MODE] Loaded {len(cross_map)} items from cross-mode JSON: {json_path}")
    except Exception as e:
        print(f"[CROSS-MODE][WARN] Failed to load cross-mode JSON: {e}")

    return cross_map


def _load_same_day_items(json_path: str) -> dict:
    """
    Load the current day's existing JSON file for incremental appending.
    Returns a dict mapping hn_id -> item dict for quick lookup.
    Used by top stories to merge new items into existing ones.
    """
    if not os.path.exists(json_path):
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) or []
        existing_map = {}
        for item in items:
            hn = item.get("hn", {})
            hn_id = hn.get("id")
            if hn_id:
                existing_map[int(hn_id)] = item
        print(f"[INCREMENTAL] Loaded {len(existing_map)} existing items from today's JSON: {json_path}")
        return existing_map
    except Exception as e:
        print(f"[INCREMENTAL][WARN] Failed to load today's JSON: {e}")
        return {}


def _load_historical_story_index(base_dir: str) -> dict:
    """Map HN id to its previously generated daily page using search_index.json."""
    index_path = os.path.join(base_dir, "search_index.json")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return {
            int(entry["id"]): entry.get("page", "")
            for entry in entries
            if entry.get("id") and entry.get("page")
        }
    except Exception as e:
        print(f"[HISTORY][WARN] Historical search index unavailable: {e}")
        return {}


def _find_historical_item(
    base_dir: str,
    historical_index: dict,
    hn_id: int,
    file_cache: dict,
) -> Optional[dict]:
    """Load one prior full item lazily from the page recorded in the index."""
    page = historical_index.get(int(hn_id), "")
    if not page:
        return None
    json_path = page.lstrip("/") + ".json"
    if not json_path.startswith(base_dir + os.sep) and not json_path.startswith(base_dir + "/"):
        return None
    if json_path not in file_cache:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_cache[json_path] = {
                int(item.get("hn", {}).get("id")): item
                for item in (data.get("items", []) or [])
                if item.get("hn", {}).get("id")
            }
        except Exception:
            file_cache[json_path] = {}
    return file_cache[json_path].get(int(hn_id))

def _is_same_story(prev_item: dict, title_en: str) -> bool:
    """
    Verify that the previous item is the same story by comparing title.
    Uses a rough match: check if the titles are substantially similar.
    """
    prev_title = prev_item.get("title_en", "")
    if not prev_title or not title_en:
        return False
    # Exact match
    if prev_title.strip().lower() == title_en.strip().lower():
        return True
    # Rough match: check if one contains the other (handles minor edits)
    a = prev_title.strip().lower()
    b = title_en.strip().lower()
    if len(a) > 10 and len(b) > 10:
        if a in b or b in a:
            return True
        # Check word overlap ratio
        words_a = set(a.split())
        words_b = set(b.split())
        if len(words_a) > 0 and len(words_b) > 0:
            overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
            if overlap > 0.8:
                return True
    return False


# ============================================================
# Rebuild all from JSON
# ============================================================

def rebuild_all_from_json(cfg: dict, max_items: int = 3650):
    """
    Rebuild ALL historical *_stories_*.md strictly from existing JSON backups.
    - No HN API
    - No LLM enrichment (uses existing summaries)
    - Tags items if not already tagged
    - Overwrites md files in place
    """
    base_dir = cfg["output"]["base_dir"]  # "hackernews"
    # Match both best_stories_*.json and top_stories_*.json
    pattern_best = os.path.join(base_dir, "*", "*", "*", "best_stories_*.json")
    pattern_top = os.path.join(base_dir, "*", "*", "*", "top_stories_*.json")
    json_paths = sorted(set(glob.glob(pattern_best) + glob.glob(pattern_top)))

    if not json_paths:
        print(f"[REBUILD] No JSON backups found.")
        return

    llm_cfg = cfg.get("llm", {})
    tag_model = llm_cfg.get("tag_model", "gpt-5-nano")
    tag_fallback = llm_cfg.get("tag_fallback_model", "gpt-4.1-nano")
    max_retries = int(llm_cfg.get("max_retries", 2))

    json_paths = json_paths[:max_items]

    print(f"[REBUILD] Found {len(json_paths)} json backups. Rebuilding md pages...")
    print(f"[REBUILD] Tag model: {tag_model}, fallback: {tag_fallback}")

    rebuilt = 0
    for json_path in json_paths:
        try:
            # Tag items if not already tagged
            try:
                tag_json_file(
                    json_path,
                    model=tag_model,
                    fallback_model=tag_fallback,
                    max_retries=max_retries,
                )
            except Exception as te:
                print(f"[REBUILD][WARN] Tag generation failed for {json_path}: {te}")

            backup = read_backup_json(json_path)
            items = backup.get("items", []) or []
            meta = backup.get("meta", {}) or {}

            # Compute hot_score for each item if not already present
            _need_hot = any("hot_score" not in it for it in items)
            if _need_hot:
                # Use scrape time from meta, or fall back to current time
                _run_utc = meta.get("run_time_utc", "")
                if _run_utc:
                    import datetime as _dt
                    try:
                        _scrape_ts = _dt.datetime.strptime(_run_utc.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp()
                    except Exception:
                        _scrape_ts = time.time()
                else:
                    _scrape_ts = time.time()
                _gravity = 1.8
                for _it in items:
                    _hn = _it.get("hn", {}) or {}
                    _score = _hn.get("score", 0)
                    _ctime = _hn.get("time", 0)
                    _age_h = max((_scrape_ts - _ctime) / 3600.0, 0.1) if _ctime else 9999
                    _hot = max(_score - 1, 0) / ((_age_h + 2) ** _gravity)
                    _it["hot_score"] = round(_hot, 2)

            # Sort by hot_score descending so default page order is by hotness
            items.sort(key=lambda x: x.get("hot_score", 0), reverse=True)

            if _need_hot:
                # Save updated JSON with hot_score (now sorted by hot_score)
                write_backup_json(json_path, meta=meta, items=items)

            md_path = json_path[:-5] + ".md"

            content_date = meta.get("content_date", "")
            story_mode = meta.get("mode", "best")
            mode_label = "Trending" if story_mode == "top" else "Daily Best"

            page_title = f"Hacker News — {mode_label} ({content_date})" if content_date else f"Hacker News — {mode_label}"
            scrape_disp = meta.get("scrape_time_display", meta.get("run_time_local", ""))
            if scrape_disp:
                page_subtitle = f"Scraped at {scrape_disp}"
            else:
                page_subtitle = ""

            md = render_markdown(
                items,
                page_title=page_title,
                page_subtitle=page_subtitle,
                html_title=page_title,
            )
            md = _clean_hn_markdown(md)

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)

            rebuilt += 1
            print(f"[REBUILD] OK: {md_path} ({len(items)} items)")
        except Exception as e:
            print(f"[REBUILD][WARN] Failed for {json_path}: {e}")

    # Rebuild index once at the end
    index_path = os.path.join(base_dir, "index.md")
    update_hackernews_index(
        base_dir=base_dir,
        index_path=index_path,
    )

    # Build search index
    build_search_index(base_dir=base_dir)

    # Build tag cloud data
    build_tag_cloud(base_dir=base_dir)
    # Build tag trend data (stream graph)
    build_tag_trend(base_dir=base_dir)
    # Build RSS feed
    build_rss_feed(base_dir=base_dir)
    # Build share pages for OG previews (needs repo root, not base_dir)
    build_share_pages(".")


    # Clean index too
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            idx_md = f.read()
        idx_md = _clean_hn_markdown(idx_md)
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(idx_md)
    except Exception as e:
        print(f"[REBUILD][WARN] Failed to clean index markdown: {e}")

    print(f"[REBUILD] Done. Rebuilt {rebuilt} md pages + index.")


# ============================================================
# Main pipeline: fetch, enrich, deduplicate, render
# ============================================================

def run_scrape(mode: str, cfg: dict, edition: str = "full"):
    """
    Run the scraping pipeline for a given mode ('best' or 'top').

    Both modes use the same unified incremental pipeline:
      - Same-day dedup: reuse LLM summaries from today's existing JSON (update scores)
      - Cross-day dedup: reuse LLM summaries from previous day's JSON
      - Merge: combine new items with existing same-day items not in current fetch
      - Cap: top morning=50, top full=100 (one same-day page/URL)
      - Sort: all items sorted by score descending
    """
    t_start = time.time()
    reset_session_stats()  # Reset token accumulator for this run

    tz_name = cfg["timezone"]

    # Real run time (used in subtitle "Scraped at ...")
    run_dt = now_in_tz(tz_name)

    # Content date: best stories = previous day, top stories = today
    if mode == "best":
        content_dt = run_dt - timedelta(days=1)
    else:
        content_dt = run_dt

    tz_abbr = run_dt.tzname() or "PT"
    scrape_time_str = f"{fmt(run_dt, cfg['format']['datetime_format'])} ({tz_abbr})"

    base_dir = cfg["output"]["base_dir"]  # hackernews
    date_dir = fmt(content_dt, cfg["format"]["date_dir_format"])  # YYYY/MM/DD
    out_dir = os.path.join(base_dir, date_dir)
    ensure_dir(out_dir)

    # Mode-specific config
    mode_cfg = cfg.get(mode, {})
    if mode == "top":
        if edition not in ("morning", "full"):
            raise ValueError("top edition must be 'morning' or 'full'")
        count_key = "morning_count" if edition == "morning" else "full_count"
        count = int(mode_cfg.get(count_key, 50 if edition == "morning" else 100))
        edition_label = "Morning 50" if edition == "morning" else "All 100"
        mode_label = f"Daily Top Stories — {edition_label}"
    else:
        count = int(mode_cfg.get("count", 50))
        edition_label = ""
        mode_label = "Daily Best"
    prefix = mode_cfg.get("filename_prefix", f"{mode}_stories")

    filename = f"{prefix}_{mmddyyyy(content_dt)}.md"
    out_path = os.path.join(out_dir, filename)

    llm_cfg = cfg.get("llm", {})
    llm_model = llm_cfg.get("model", "gpt-5-nano")
    llm_fallback = llm_cfg.get("fallback_model", "gpt-5-mini")
    tag_model = llm_cfg.get("tag_model", "gpt-5-nano")
    tag_fallback = llm_cfg.get("tag_fallback_model", "gpt-4.1-nano")
    max_retries = int(llm_cfg.get("max_retries", 2))

    img_cfg = cfg.get("images", {})
    img_enabled = bool(img_cfg.get("enabled", True))
    img_timeout = int(img_cfg.get("timeout_seconds", 15))
    img_ua = img_cfg.get("user_agent", "Mozilla/5.0")
    article_cfg = cfg.get("article_context", {})
    article_context_enabled = bool(article_cfg.get("enabled", True))
    article_context_max_chars = int(article_cfg.get("max_chars", 4000))

    # ---------- Backup JSON (source of truth) ----------
    json_name = filename.replace(".md", ".json")
    json_path = os.path.join(out_dir, json_name)

    json_exists = os.path.exists(json_path)
    now_utc = utc_now()

    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    is_scheduled = (event_name == "schedule")

    # Both modes use the same unified incremental pipeline
    stories_max = count if mode == "top" else BEST_STORIES_MAX

    print("=" * 70)
    print(f"[PIPELINE] Hacker News Daily Scraper — mode={mode}")
    print(f"[PIPELINE] event={event_name} | is_scheduled={is_scheduled}")
    print(f"[PIPELINE] content_date={content_dt.strftime('%Y-%m-%d')} | run_local={scrape_time_str}")
    print(f"[PIPELINE] run_utc={now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"[PIPELINE] json={json_path} | exists={json_exists}")
    print(f"[PIPELINE] llm_model={llm_model} | fallback={llm_fallback}")
    print(f"[PIPELINE] tag_model={tag_model} | tag_fallback={tag_fallback}")
    print(f"[PIPELINE] max_retries={max_retries}")
    print(f"[PIPELINE] stories_max={stories_max} | incremental=True")
    print("=" * 70)

    # LLM is always enabled for new items
    llm_enabled = True

    # Load the same-day page before fetching. Existing IDs are refreshed first;
    # then current HN Top IDs are appended until the edition target is reached.
    same_day_map = _load_same_day_items(json_path)

    # ========== STEP 1: Fetch story IDs ==========
    print(f"\n[STEP 1/6] Fetching top {count} {mode} story IDs from HN API ...")
    t0 = time.time()
    current_ids = get_story_ids(mode)
    ids = _ordered_unique_ids(same_day_map.keys(), current_ids)
    print(
        f"[STEP 1/6] Got {len(current_ids)} source IDs; "
        f"refreshing {len(same_day_map)} same-day IDs before filling target={count} "
        f"in {time.time() - t0:.1f}s"
    )

    # ========== STEP 2: Fetch story details ==========
    print(f"\n[STEP 2/6] Fetching story details ...")
    t0 = time.time()
    raw_items = []
    skipped = 0
    for item_id in ids:
        if len(raw_items) >= count:
            break
        try:
            item = get_item(int(item_id))
        except Exception as e:
            print(f"  [WARN] Failed to fetch item {item_id}: {e}. Skipping.")
            skipped += 1
            continue
        if not item or item.get("type") != "story":
            skipped += 1
            continue
        title_en = (item.get("title") or "").strip()
        if not title_en:
            skipped += 1
            continue
        url = get_item_url(item)
        hn_id = int(item_id)
        hn_type = item.get("type")
        hn_by = item.get("by")
        hn_score = item.get("score")
        hn_desc = item.get("descendants")
        hn_time = item.get("time")  # unix timestamp (seconds)
        hn_text = html.unescape(re.sub(r"<[^>]+>", " ", item.get("text") or ""))
        hn_text = " ".join(hn_text.split())

        raw_items.append({
            "id": hn_id,
            "title_en": title_en,
            "url": url,
            "hn_text": hn_text,
            "hn_time": int(hn_time) if hn_time is not None else None,
            "hn_type": hn_type,
            "hn_by": hn_by,
            "hn_score": int(hn_score) if hn_score is not None else None,
            "hn_descendants": int(hn_desc) if hn_desc is not None else None,
        })

    print(f"[STEP 2/6] Fetched {len(raw_items)} valid stories, skipped {skipped}, in {time.time() - t0:.1f}s")

    if len(raw_items) < count:
        raise RuntimeError(
            f"Only {len(raw_items)} valid stories were fetched; "
            f"refusing to publish an incomplete {edition_label or mode_label} target of {count}."
        )

    # ========== STEP 3: Deduplication ==========
    print(f"\n[STEP 3/6] Deduplication ...")
    t0 = time.time()

    # Load previous day items for cross-day dedup (same mode)
    prev_items = _load_previous_day_items(base_dir, content_dt, mode)

    # Load cross-mode items (best↔top) for additional dedup
    cross_mode_items = _load_cross_mode_items(base_dir, run_dt, content_dt, mode)
    historical_index = _load_historical_story_index(base_dir)
    historical_file_cache = {}

    reused_same_day = 0
    reused_cross_day = 0
    reused_cross_mode = 0
    reused_history = 0
    new_items_for_llm = []
    reused_map = {}  # id -> prev_item (items that can skip LLM)
    score_update_map = {}  # id -> updated score/descendants for reused items

    for it in raw_items:
        hn_id = it["id"]
        title_en = it["title_en"]

        # Priority 1: Check same-day existing items (incremental dedup)
        if hn_id in same_day_map:
            prev = same_day_map[hn_id]
            if _is_same_story(prev, title_en):
                has_summary = (
                    prev.get("summary_en") and
                    prev.get("summary_zh") and
                    prev.get("title_zh") and
                    prev["summary_en"] != "Brief intro unavailable (LLM disabled)."
                )
                if has_summary:
                    reused_map[hn_id] = prev
                    # Track updated score/descendants
                    score_update_map[hn_id] = {
                        "score": it.get("hn_score"),
                        "descendants": it.get("hn_descendants"),
                    }
                    reused_same_day += 1
                    continue

        # Priority 2: Check previous day's items (cross-day dedup, same mode)
        if hn_id in prev_items:
            prev = prev_items[hn_id]
            if _is_same_story(prev, title_en):
                has_summary = (
                    prev.get("summary_en") and
                    prev.get("summary_zh") and
                    prev.get("title_zh") and
                    prev["summary_en"] != "Brief intro unavailable (LLM disabled)."
                )
                if has_summary:
                    reused_map[hn_id] = prev
                    score_update_map[hn_id] = {
                        "score": it.get("hn_score"),
                        "descendants": it.get("hn_descendants"),
                    }
                    reused_cross_day += 1
                    continue

        # Priority 3: Check cross-mode items (best↔top dedup)
        if hn_id in cross_mode_items:
            prev = cross_mode_items[hn_id]
            if _is_same_story(prev, title_en):
                has_summary = (
                    prev.get("summary_en") and
                    prev.get("summary_zh") and
                    prev.get("title_zh") and
                    prev["summary_en"] != "Brief intro unavailable (LLM disabled)."
                )
                if has_summary:
                    reused_map[hn_id] = prev
                    score_update_map[hn_id] = {
                        "score": it.get("hn_score"),
                        "descendants": it.get("hn_descendants"),
                    }
                    reused_cross_mode += 1
                    continue

        # Priority 4: Any older generated page indexed by HN id. This makes
        # reuse global without loading every historical JSON on every run.
        historical = _find_historical_item(
            base_dir, historical_index, hn_id, historical_file_cache
        )
        if historical and _is_same_story(historical, title_en):
            has_summary = (
                historical.get("summary_en") and
                historical.get("summary_zh") and
                historical.get("title_zh") and
                historical["summary_en"] != "Brief intro unavailable (LLM disabled)."
            )
            if has_summary:
                reused_map[hn_id] = historical
                score_update_map[hn_id] = {
                    "score": it.get("hn_score"),
                    "descendants": it.get("hn_descendants"),
                }
                reused_history += 1
                continue

        new_items_for_llm.append(it)

    print(f"[STEP 3/6] Dedup result:")
    print(f"  Same-day reused: {reused_same_day}")
    print(f"  Cross-day reused: {reused_cross_day}")
    print(f"  Cross-mode reused: {reused_cross_mode}")
    print(f"  Historical reused: {reused_history}")
    print(f"  New (need LLM): {len(new_items_for_llm)}")
    print(f"[STEP 3/6] Completed in {time.time() - t0:.1f}s")

    # Fetch each new source page once before LLM enrichment. The article
    # excerpt is transient prompt context; the preview image is reused later.
    if new_items_for_llm and (article_context_enabled or img_enabled):
        print(f"\n[SOURCE] Fetching context for {len(new_items_for_llm)} new items ...")
        for it in new_items_for_llm:
            hn_context = (it.get("hn_text") or "")[:article_context_max_chars]
            page = fetch_page_context(
                it["url"],
                timeout_seconds=img_timeout,
                user_agent=img_ua,
                max_article_chars=(
                    article_context_max_chars
                    if article_context_enabled and not hn_context
                    else 0
                ),
            )
            it["article_context"] = hn_context or page.get("article_context") or ""
            it["prefetched_image_url"] = page.get("image_url") if img_enabled else None
        context_count = sum(bool(it.get("article_context")) for it in new_items_for_llm)
        context_chars = sum(len(it.get("article_context") or "") for it in new_items_for_llm)
        print(f"[SOURCE] Article context available for {context_count}/{len(new_items_for_llm)} items")
        print(f"[SOURCE] Total bounded context: {context_chars:,} chars")

    # ========== STEP 4: LLM enrichment (only for new items) ==========
    print(f"\n[STEP 4/6] LLM enrichment for {len(new_items_for_llm)} new items (model={llm_model}, fallback={llm_fallback}) ...")
    enrich_map = {}
    if llm_enabled and new_items_for_llm:
        try:
            enrich_map = llm_enrich_batch(new_items_for_llm, model=llm_model, max_retries=max_retries)
            print(f"[STEP 4/6] LLM enrichment succeeded with model={llm_model}")
        except Exception as e:
            print(f"[STEP 4/6][WARN] LLM failed with model={llm_model}: {e}")
            if llm_fallback and llm_fallback != llm_model:
                print(f"[STEP 4/6] Retrying with fallback model={llm_fallback} ...")
                try:
                    enrich_map = llm_enrich_batch(new_items_for_llm, model=llm_fallback, max_retries=max_retries)
                    print(f"[STEP 4/6] LLM enrichment succeeded with fallback={llm_fallback}")
                except Exception as e2:
                    print(f"[STEP 4/6][ERROR] Fallback also failed: {e2}")
                    raise
            else:
                raise
    elif not new_items_for_llm:
        print(f"[STEP 4/6] All items reused — no LLM calls needed!")

    # ========== STEP 5: Fetch preview images & assemble final items ==========
    print(f"\n[STEP 5/6] Fetching preview images (enabled={img_enabled}) ...")
    t0 = time.time()

    # Build the list of newly fetched items (from this run)
    new_final_items = []
    img_found = 0
    for it in raw_items:
        hn_time = it.get("hn_time")
        created_display = ""
        if hn_time:
            created_dt = datetime.fromtimestamp(int(hn_time), tz=tz.gettz(tz_name))
            created_display = created_dt.strftime("Created: %b %d, %Y / %H:%M PT")

        _id = it["id"]
        title_en = it["title_en"]
        url = it["url"]

        # Check if this item was reused (same-day or cross-day)
        if _id in reused_map:
            prev = reused_map[_id]
            title_zh = prev.get("title_zh", "")
            summary_en = prev.get("summary_en", "")
            summary_zh = prev.get("summary_zh", "")
            image_url = prev.get("image_url")
            if image_url:
                img_found += 1
            tags = prev.get("tags", [])

            # For reused items (same-day or cross-day), update score/descendants to latest
            if _id in score_update_map:
                updated = score_update_map[_id]
                hn_score_new = updated.get("score", it.get("hn_score"))
                hn_desc_new = updated.get("descendants", it.get("hn_descendants"))
            else:
                hn_score_new = it.get("hn_score")
                hn_desc_new = it.get("hn_descendants")

            print(f"  [REUSE] ID={_id}: \"{title_en[:50]}\" — reused summary + image + tags")
        elif llm_enabled and _id in enrich_map:
            extra = enrich_map[_id]
            title_zh = extra["title_zh"]
            summary_en = extra["summary_en"]
            summary_zh = extra["summary_zh"]
            image_url = it.get("prefetched_image_url") if img_enabled else None
            tags = []
            hn_score_new = it.get("hn_score")
            hn_desc_new = it.get("hn_descendants")
            if image_url:
                img_found += 1
        else:
            title_zh = "（未启用翻译）" + title_en
            summary_en = "Brief intro unavailable (LLM disabled)."
            summary_zh = "（未启用简介翻译）"
            image_url = None
            tags = []
            hn_score_new = it.get("hn_score")
            hn_desc_new = it.get("hn_descendants")
            image_url = it.get("prefetched_image_url") if img_enabled else None
            if image_url:
                img_found += 1

        comments_url = f"https://news.ycombinator.com/item?id={_id}"

        item_dict = {
            "title_en": title_en,
            "url": url,
            "title_zh": title_zh,
            # NEW is scoped to this day's page: it appears only on stories
            # introduced by the current run and disappears on the next run.
            "is_new": _id not in same_day_map,
            "created_display": created_display,
            "image_url": image_url,
            "summary_en": summary_en,
            "summary_zh": summary_zh,
            "hn": {
                "id": _id,
                "type": it.get("hn_type"),
                "by": it.get("hn_by"),
                "score": hn_score_new,
                "descendants": hn_desc_new,
                "time": it.get("hn_time"),
                "comments_url": comments_url,
            },
        }
        if tags:
            item_dict["tags"] = tags

        new_final_items.append(item_dict)

    print(f"[STEP 5/6] Images: {img_found}/{len(new_final_items)} found in {time.time() - t0:.1f}s")

    # ---------- Merge with existing same-day items (both modes) ----------
    if same_day_map:
        # Carry over existing items that are NOT in the new fetch
        new_ids = {it["hn"]["id"] for it in new_final_items}
        carried_over = []
        for hn_id, existing_item in same_day_map.items():
            if hn_id not in new_ids:
                carried_over.append(existing_item)

        final_items = new_final_items + carried_over
        print(f"[INCREMENTAL] Merged: {len(new_final_items)} from this run + {len(carried_over)} carried over = {len(final_items)} total")
    else:
        final_items = new_final_items

    # ---------- Sort by score descending and cap at stories_max ----------
    final_items.sort(key=lambda x: (x.get("hn", {}).get("score") or 0), reverse=True)
    if len(final_items) > stories_max:
        print(f"[CAP] Capping from {len(final_items)} to {stories_max} items (by score)")
        final_items = final_items[:stories_max]
    if mode == "top" and len(final_items) != count:
        raise RuntimeError(
            f"Expected exactly {count} unique stories for {edition_label}, "
            f"but assembled {len(final_items)}. Existing daily files were not overwritten."
        )
    print(f"[SORT] Sorted {len(final_items)} items by score (top: {final_items[0].get('hn',{}).get('score') if final_items else 'N/A'})")

    # ---------- Build meta ----------
    meta = {
        "mode": mode,
        "source": "https://news.ycombinator.com/",
        "api": "https://github.com/HackerNews/API",
        "count_requested": count,
        "count_written": len(final_items),
        "reused_same_day": reused_same_day,
        "reused_cross_day": reused_cross_day,
        "reused_history": reused_history,
        "new_llm_enriched": len(new_items_for_llm),
        "scrape_time_display": scrape_time_str,
        "timezone": tz_name,
        "date_dir": date_dir,
        "content_date": content_dt.strftime("%Y-%m-%d"),
        "edition": edition if mode == "top" else "best",
        "edition_label": edition_label,
        "target_count": count,
        "run_time_local": scrape_time_str,
        "run_time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    meta["incremental"] = True
    meta["stories_max"] = stories_max

    # Compute hot_score for each item at scrape time
    _now_ts = time.time()
    _gravity = 1.8
    for _it in final_items:
        _hn = _it.get("hn", {}) or {}
        _score = _hn.get("score", 0)
        _ctime = _hn.get("time", 0)
        _age_h = max((_now_ts - _ctime) / 3600.0, 0.1) if _ctime else 9999
        _hot = max(_score - 1, 0) / ((_age_h + 2) ** _gravity)
        _it["hot_score"] = round(_hot, 2)
    meta["hot_score_time_utc"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_now_ts))

    # Re-sort by hot_score descending so JSON/HTML default order is by hotness
    final_items.sort(key=lambda x: x.get("hot_score", 0), reverse=True)
    print(f"[SORT] Re-sorted {len(final_items)} items by hot_score (top: {final_items[0].get('hot_score') if final_items else 'N/A'})")

    write_backup_json(json_path, meta=meta, items=final_items)
    print(f"\n[JSON] Saved backup: {json_path} ({len(final_items)} items, same_day_reused={reused_same_day}, cross_day_reused={reused_cross_day})")

    # ========== STEP 6: Generate tags ==========
    print(f"\n[STEP 6/6] Generating tags (model={tag_model}, fallback={tag_fallback}) ...")
    try:
        tag_json_file(
            json_path,
            model=tag_model,
            fallback_model=tag_fallback,
            max_retries=max_retries,
        )
        print(f"[STEP 6/6] Tag generation succeeded")
    except Exception as e:
        print(f"[STEP 6/6][ERROR] Tag generation failed: {e}")
        print(f"[STEP 6/6][ERROR] Continuing without tags ...")

    # ---------- Render MD strictly from JSON backup ----------
    backup = read_backup_json(json_path)
    items_for_render = backup["items"]

    has_tags = sum(1 for it in items_for_render if it.get("tags"))

    page_title = f"Hacker News — {mode_label} ({content_dt.strftime('%Y-%m-%d')})"
    page_subtitle = f"Scraped at {scrape_time_str}"

    md = render_markdown(
        items_for_render,
        page_title=page_title,
        page_subtitle=page_subtitle,
        html_title=page_title,
    )
    md = _clean_hn_markdown(md)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n[MD] Rendered: {out_path}")

    elapsed = time.time() - t_start
    print("\n" + "=" * 70)
    print(f"[DONE] Pipeline completed in {elapsed:.1f}s")
    print(f"[DONE] {out_path} — {len(items_for_render)} items ({has_tags} with tags)")
    print(f"[DONE] mode={mode}, content_date={content_dt.strftime('%Y-%m-%d')}, run={scrape_time_str}")
    print(f"[DONE] Same-day reused: {reused_same_day}, Cross-day reused: {reused_cross_day}, Historical reused: {reused_history}, New LLM: {len(new_items_for_llm)}")
    print("=" * 70)

    # Log this scrape run to scrape_run_log.md
    try:
        session = get_session_stats()
        trigger = "schedule" if is_scheduled else (
            "manual" if event_name == "workflow_dispatch" else "local"
        )
        log_scrape_run(
            mode=mode,
            trigger=trigger,
            duration_sec=elapsed,
            total_items=len(items_for_render),
            new_llm=len(new_items_for_llm),
            reused_same_day=reused_same_day,
            reused_cross_day=reused_cross_day + reused_history,
            total_tokens=session["total_tokens"],
            total_cost=session["total_cost"],
            note=edition_label,
        )
    except Exception as e:
        print(f"[WARN] Failed to write scrape run log: {e}")


def main():
    t_start = time.time()

    if len(sys.argv) < 2:
        print("Usage: python news_scraper/main.py best|top [morning|full]|all|rebuild")
        sys.exit(2)

    mode = sys.argv[1].strip().lower()
    if mode not in ("best", "top", "all", "rebuild"):
        raise ValueError("Usage: python news_scraper/main.py best|top|all|rebuild")

    cfg = load_config("news_config.yml")
    print(f"[CONFIG] Loaded news_config.yml")

    if mode == "rebuild":
        rebuild_all_from_json(cfg)
        return

    edition = sys.argv[2].strip().lower() if len(sys.argv) >= 3 else "full"
    if mode == "top" and edition not in ("morning", "full"):
        raise ValueError("Usage: python news_scraper/main.py top [morning|full]")

    # For 'all' mode, run both best and top sequentially
    modes_to_run = ["best", "top"] if mode == "all" else [mode]

    for m in modes_to_run:
        print(f"\n{'#' * 70}")
        print(f"# Running mode: {m}")
        print(f"{'#' * 70}\n")
        run_scrape(m, cfg, edition=edition if m == "top" else "full")

    # Update index page ONCE after all modes are done
    base_dir = cfg["output"]["base_dir"]
    index_path = os.path.join(base_dir, "index.md")
    update_hackernews_index(
        base_dir=base_dir,
        index_path=index_path,
    )

    # Build tag cloud data
    build_tag_cloud(base_dir=base_dir)
    # Build tag trend data (stream graph)
    build_tag_trend(base_dir=base_dir)
    # Build RSS feed
    build_rss_feed(base_dir=base_dir)
    # Build share pages for OG previews (needs repo root, not base_dir)
    build_share_pages(".")


    # Clean index page
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            idx_md = f.read()
        idx_md = _clean_hn_markdown(idx_md)
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(idx_md)
    except Exception as e:
        print(f"[WARN] Failed to clean index markdown: {e}")

    # Log daily token usage summary
    try:
        log_daily_summary()
    except Exception as e:
        print(f"[WARN] Failed to write token usage summary: {e}")

    elapsed = time.time() - t_start
    print(f"\n[TOTAL] All modes completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
