import os
import re
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Tuple

BEST_JSON_RE = re.compile(r"^best_stories_(\d{8})\.json$")   # MMDDYYYY
TOP_JSON_RE = re.compile(r"^top_stories_(\d{8})\.json$")     # MMDDYYYY
BEST_MD_RE = re.compile(r"^best_stories_(\d{8})\.md$")       # MMDDYYYY
TOP_MD_RE = re.compile(r"^top_stories_(\d{8})\.md$")         # MMDDYYYY
WEEKLY_JSON_RE = re.compile(r"^(\d{4})-W(\d{2})\.json$")     # YYYY-WNN
MONTHLY_JSON_RE = re.compile(r"^(\d{4})-(\d{2})\.json$")      # YYYY-MM


@dataclass
class StoryEntry:
    """One story type (best or top) for a given date."""
    rel_url: str               # /hackernews/YYYY/MM/DD/best_stories_MMDDYYYY
    story_type: str            # "best" or "top"
    count_written: Optional[int] = None
    top_tags: List[Tuple[str, int]] = field(default_factory=list)
    edition: str = ""             # "morning" / "full" for unified future top pages
    # e.g. [("AI", 10), ("Programming", 8)]


@dataclass
class DayEntry:
    """All story entries for a single content_date."""
    content_date: str          # YYYY-MM-DD
    stories: List[StoryEntry] = field(default_factory=list)


def _try_parse_dt_from_dir(date_dir: str) -> Optional[datetime]:
    try:
        y, m, d = date_dir.split("/")
        return datetime(int(y), int(m), int(d))
    except Exception:
        return None


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _extract_top_tags(items: list, n: int = 2) -> List[Tuple[str, int]]:
    """Extract the top-N most frequent tags from a list of story items."""
    tag_counter: Counter = Counter()
    for item in items:
        tags = item.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    tag_counter[tag.strip()] += 1
    return tag_counter.most_common(n)


def _collect_day_entries(base_dir: str) -> List[DayEntry]:
    """
    Collect all day entries from JSON backups (both best and top).
    Groups entries by content_date.
    """
    # date_str -> DayEntry
    day_map: Dict[str, DayEntry] = {}

    if not os.path.isdir(base_dir):
        return []

    # Pass 1: JSON backups (preferred)
    for root, _, files in os.walk(base_dir):
        rel_dir = os.path.relpath(root, base_dir).replace("\\", "/")
        if rel_dir.startswith("."):
            continue

        dt_dir = _try_parse_dt_from_dir(rel_dir)

        for fn in files:
            # Determine story type
            m_best = BEST_JSON_RE.match(fn)
            m_top = TOP_JSON_RE.match(fn)
            if not m_best and not m_top:
                continue

            story_type = "best" if m_best else "top"
            abs_path = os.path.join(root, fn)
            data = _read_json(abs_path)
            if not data:
                continue

            meta = data.get("meta", {}) or {}
            items = data.get("items", []) or []

            content_date = meta.get("content_date")
            if not content_date and dt_dir is not None:
                content_date = dt_dir.strftime("%Y-%m-%d")
            if not content_date:
                continue

            # Always use actual item count from JSON (not meta.count_written)
            count_written = len(items)

            # Extract top 2 most frequent tags
            top_tags = _extract_top_tags(items, n=2)

            rel_no_ext = fn[:-5]  # strip .json
            rel_url = f"/{base_dir}/{rel_dir}/{rel_no_ext}".replace("//", "/")

            entry = StoryEntry(
                rel_url=rel_url,
                story_type=story_type,
                count_written=count_written,
                top_tags=top_tags,
                edition=meta.get("edition", ""),
            )

            if content_date not in day_map:
                day_map[content_date] = DayEntry(content_date=content_date)
            day_map[content_date].stories.append(entry)

    # Pass 2: MD fallback (for dates with no JSON)
    have_dates_types = set()
    for date_str, day in day_map.items():
        for s in day.stories:
            have_dates_types.add((date_str, s.story_type))

    for root, _, files in os.walk(base_dir):
        rel_dir = os.path.relpath(root, base_dir).replace("\\", "/")
        if rel_dir.startswith("."):
            continue

        dt_dir = _try_parse_dt_from_dir(rel_dir)
        if dt_dir is None:
            continue
        fallback_date = dt_dir.strftime("%Y-%m-%d")

        for fn in files:
            m_best = BEST_MD_RE.match(fn)
            m_top = TOP_MD_RE.match(fn)
            if not m_best and not m_top:
                continue

            story_type = "best" if m_best else "top"
            if (fallback_date, story_type) in have_dates_types:
                continue

            rel_url = f"/{base_dir}/{rel_dir}/{fn[:-3]}".replace("//", "/")
            entry = StoryEntry(
                rel_url=rel_url,
                story_type=story_type,
            )

            if fallback_date not in day_map:
                day_map[fallback_date] = DayEntry(content_date=fallback_date)
            day_map[fallback_date].stories.append(entry)

    # Sort by content_date desc
    days = sorted(day_map.values(), key=lambda d: d.content_date, reverse=True)

    # Sort stories within each day: best first, then top
    type_order = {"best": 0, "top": 1}
    for day in days:
        day.stories.sort(key=lambda s: type_order.get(s.story_type, 99))

    return days


def _compute_stats(days: List[DayEntry]) -> dict:
    """Compute aggregate statistics across all day entries."""
    total_stories = 0
    best_count = 0
    top_count = 0
    dates = set()

    for day in days:
        dates.add(day.content_date)
        for s in day.stories:
            n = s.count_written or 0
            total_stories += n
            if s.story_type == "best":
                best_count += 1
            else:
                top_count += 1

    sorted_dates = sorted(dates)
    date_range_start = sorted_dates[0] if sorted_dates else ""
    date_range_end = sorted_dates[-1] if sorted_dates else ""

    return {
        "total_days": len(dates),
        "total_stories": total_stories,
        "best_files": best_count,
        "top_files": top_count,
        "date_start": date_range_start,
        "date_end": date_range_end,
    }


def _build_detail_html(entry: StoryEntry) -> str:
    """
    Build the detail text for a story row.
    Format: All N · Tag1 X · Tag2 Y
    Uses plain text style with bold numbers matching the stats bar.
    """
    parts = []

    # Unified future top pages expose their publication stage. Historical
    # Trending/Best entries have no edition metadata and retain "All N".
    count = entry.count_written
    if count is not None:
        if entry.story_type == "top" and entry.edition == "morning":
            parts.append(f"Morning <b>{count}</b>")
        else:
            parts.append(f"All <b>{count}</b>")

    # Top tags: "AI 10 · Programming 8"
    for tag_name, tag_count in entry.top_tags:
        parts.append(f"{tag_name} <b>{tag_count}</b>")

    if not parts:
        return ""

    sep = ' <span class="hn-row-sep">·</span> '
    return sep.join(parts)



def _compute_hot_score(score: int, created_ts: int, ref_ts: float, gravity: float = 1.8) -> float:
    """Compute HN time-decay hotness: (P-1) / (T+2)^G"""
    age_hours = max((ref_ts - created_ts) / 3600.0, 0.1) if created_ts else 9999
    return max(score - 1, 0) / ((age_hours + 2) ** gravity)


def _get_top_stories(base_dir: str, days: List[DayEntry], n: int = 10) -> List[dict]:
    """
    Get the top N stories sorted by hot_score descending from the latest
    Trending (top) JSON. Computes hot_score on the fly if not stored in JSON
    (using run_time_utc from meta as reference time).
    """
    import time as _time
    import datetime as _dt

    # Find the latest day that has a 'top' story entry
    for day in days:
        for s in day.stories:
            if s.story_type == "top":
                json_path = s.rel_url.lstrip("/") + ".json"
                if not os.path.exists(json_path):
                    continue
                data = _read_json(json_path)
                if not data:
                    continue
                items = data.get("items", []) or []
                meta = data.get("meta", {}) or {}

                # Ensure every item has hot_score
                need_compute = any("hot_score" not in it for it in items)
                if need_compute:
                    # Use scrape time from meta as reference
                    _run_utc = meta.get("run_time_utc", "")
                    if _run_utc:
                        try:
                            ref_ts = _dt.datetime.strptime(
                                _run_utc.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S"
                            ).replace(tzinfo=_dt.timezone.utc).timestamp()
                        except Exception:
                            ref_ts = _time.time()
                    else:
                        ref_ts = _time.time()
                    for it in items:
                        if "hot_score" not in it:
                            hn = it.get("hn", {}) or {}
                            it["hot_score"] = round(_compute_hot_score(
                                hn.get("score", 0), hn.get("time", 0), ref_ts
                            ), 2)

                # Sort by hot_score descending
                items.sort(
                    key=lambda x: x.get("hot_score", 0),
                    reverse=True
                )
                result = []
                for it in items[:n]:
                    hn = it.get("hn", {}) or {}
                    hn_id = hn.get("id", "")
                    result.append({
                        "title_en": it.get("title_en", ""),
                        "title_zh": it.get("title_zh", ""),
                        "url": it.get("url", ""),
                        "score": hn.get("score", 0),
                        "descendants": hn.get("descendants", 0),
                        "tags": it.get("tags", []),
                        "hn_id": hn_id,
                        "hn_time": hn.get("time", 0),
                        "daily_url": s.rel_url,
                        "content_date": day.content_date,
                        "scrape_time_display": meta.get("scrape_time_display", ""),
                        "hot_score": it.get("hot_score", 0),
                    })
                return result
    return []


def _collect_weekly_entries(base_dir: str) -> List[dict]:
    """
    Scan hackernews/weekly/ for weekly digest JSON files.
    Returns a list of dicts with url, week number, date range, and top_n.
    Sorted by week descending (newest first).
    """
    weekly_dir = os.path.join(base_dir, "weekly")
    if not os.path.isdir(weekly_dir):
        return []

    entries = []
    for fn in os.listdir(weekly_dir):
        m = WEEKLY_JSON_RE.match(fn)
        if not m:
            continue

        year, week = m.group(1), m.group(2)
        iso_week = f"{year}-W{week}"
        json_path = os.path.join(weekly_dir, fn)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        meta = data.get("meta", {}) or {}
        date_start = meta.get("date_start", "")
        date_end = meta.get("date_end", "")
        top_n = meta.get("top_n", 0)
        total_pool = meta.get("total_pool", 0)

        # Build detail text
        detail_parts = []
        if date_start and date_end:
            try:
                detail_parts.append(
                    f"{datetime.strptime(date_start, '%Y-%m-%d').strftime('%m-%d')} — "
                    f"{datetime.strptime(date_end, '%Y-%m-%d').strftime('%m-%d')}"
                )
            except ValueError:
                detail_parts.append(f"{date_start} — {date_end}")
        if total_pool:
            detail_parts.append(f"All <b>{total_pool}</b>")
        elif top_n:
            detail_parts.append(f"All <b>{top_n}</b>")

        # Add top tags from tag_stats
        tag_stats = data.get("tag_stats", [])
        if tag_stats:
            top_tags = tag_stats[:2]
            for ts in top_tags:
                detail_parts.append(f"{ts['tag']} <b>{ts['count']}</b>")

        sep = ' <span class="hn-row-sep">·</span> '
        detail = sep.join(detail_parts)

        entries.append({
            "iso_week": iso_week,
            "week": week,
            "year": year,
            "url": f"/{base_dir}/weekly/{iso_week}",
            "detail": detail,
            "sort_key": f"{year}-{week}",
        })

    # Sort newest first
    entries.sort(key=lambda x: x["sort_key"], reverse=True)
    return entries


def _collect_monthly_entries(base_dir: str) -> List[dict]:
    """Collect generated monthly digest metadata, newest first."""
    monthly_dir = os.path.join(base_dir, "monthly")
    if not os.path.isdir(monthly_dir):
        return []
    entries = []
    for fn in os.listdir(monthly_dir):
        match = MONTHLY_JSON_RE.match(fn)
        if not match:
            continue
        month_str = f"{match.group(1)}-{match.group(2)}"
        try:
            with open(os.path.join(monthly_dir, fn), "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {}) or {}
            month_dt = datetime.strptime(month_str, "%Y-%m")
            end_dt = datetime.strptime(meta.get("date_end", ""), "%Y-%m-%d")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        top_n = int(meta.get("top_n", 0) or 0)
        total_pool = int(meta.get("total_pool", 0) or 0)
        detail_parts = [f"Top <b>{top_n}</b>"]
        if total_pool > top_n:
            detail_parts.append(f"from <b>{total_pool}</b> unique stories")
        for stat in (data.get("tag_stats", []) or [])[:2]:
            detail_parts.append(f"{stat['tag']} <b>{stat['count']}</b>")
        entries.append({
            "month": month_str,
            "label": month_dt.strftime("%B %Y"),
            "url": f"/{base_dir}/monthly/{month_str}",
            "detail": ' <span class="hn-row-sep">·</span> '.join(detail_parts),
            "end_date": end_dt,
        })
    return sorted(entries, key=lambda entry: entry["month"], reverse=True)

def _group_days_by_week(days: List[DayEntry]) -> List[dict]:
    """Group DayEntry list by ISO week.

    Returns a list of dicts sorted by week descending (newest first):
    [
        {
            "iso_week": "2026-W13",
            "year": 2026,
            "week_num": 13,
            "label": "2026 Week 13",
            "days": [DayEntry, ...],  # sorted by date desc within week
        },
        ...
    ]
    """
    from collections import OrderedDict

    week_map: Dict[str, dict] = {}
    for day in days:
        try:
            dt = datetime.strptime(day.content_date, "%Y-%m-%d")
            iso_year, iso_week_num, _ = dt.isocalendar()
            iso_week = f"{iso_year}-W{iso_week_num:02d}"
        except Exception:
            continue

        if iso_week not in week_map:
            week_map[iso_week] = {
                "iso_week": iso_week,
                "year": iso_year,
                "week_num": iso_week_num,
                "label": f"{iso_year} Week {iso_week_num}",
                "days": [],
            }
        week_map[iso_week]["days"].append(day)

    # Sort weeks descending
    weeks = sorted(week_map.values(), key=lambda w: w["iso_week"], reverse=True)
    # Sort days within each week descending
    for w in weeks:
        w["days"].sort(key=lambda d: d.content_date, reverse=True)
    return weeks


def update_hackernews_index(
    base_dir: str = "hackernews",
    index_path: str = "hackernews/index.md",
    max_items: Optional[int] = None,
) -> str:
    all_days = _collect_day_entries(base_dir)
    stats = _compute_stats(all_days)
    # The archive is the navigation surface for historical pages, so it should
    # not silently hide older dates. A limit remains available only for explicit
    # callers/tests; production passes no limit and renders the full archive.
    days = all_days if max_items is None else all_days[:max_items]
    # Build weekly data lookups
    weekly_entries_list = _collect_weekly_entries(base_dir)
    weekly_map = {w["iso_week"]: w for w in weekly_entries_list}  # iso_week -> weekly entry
    monthly_entries = _collect_monthly_entries(base_dir)

    # Determine current ISO week
    now = datetime.now()
    current_iso_year, current_iso_week, _ = now.isocalendar()
    current_week_str = f"{current_iso_year}-W{current_iso_week:02d}"

    lines: List[str] = []
    lines.append("---")
    lines.append("layout: hn")
    lines.append('title: "Hacker News Daily"')
    lines.append("---")
    lines.append("")

    lines.append("<h1 class='hn-h1'>Hacker News Daily</h1>")
    source_link = "<a href='https://news.ycombinator.com/' target='_blank' rel='noopener noreferrer'>news.ycombinator.com</a>"
    lines.append(f"<p class='hn-subtitle'>Source: {source_link}</p>")

    # Statistics bar
    if stats["total_days"] > 0:
        stat_parts = []
        stat_parts.append(f"<span class='hn-stat-item'><span class='hn-stat-num'>{stats['total_days']}</span> days</span>")
        stat_parts.append(f"<span class='hn-stat-item'><span class='hn-stat-num'>{stats['total_stories']}</span> stories</span>")
        stat_parts.append(f"<span class='hn-stat-item'><span class='hn-stat-num'>{stats['best_files']}</span> daily best</span>")
        stat_parts.append(f"<span class='hn-stat-item'><span class='hn-stat-num'>{stats['top_files']}</span> trending</span>")
        date_range = f"{stats['date_start']} — {stats['date_end']}" if stats['date_start'] != stats['date_end'] else stats['date_start']
        stat_parts.append(f"<span class='hn-stat-item'>{date_range}</span>")
        stat_parts.append("<a class='hn-stat-link' href='/hackernews/trends/'>Trends</a>")
        stat_parts.append("<a class='hn-stat-link hn-rss-link' href='/hackernews/feed.xml' title='RSS Feed'>RSS</a>")

        sep = ' <span class="hn-stat-sep">·</span> '
        lines.append(f"<div class='hn-stats'>{sep.join(stat_parts)}</div>")

    # Search box
    lines.append("<div class='hn-search-box'>")
    lines.append("<input type='text' id='hn-search-input' class='hn-search-input' placeholder='Search all stories (title, tags, author...)' autocomplete='off'/>")
    lines.append("<div id='hn-search-status' class='hn-search-status'></div>")
    lines.append("<div id='hn-search-sort' class='hn-search-sort' style='display:none;'>")
    lines.append("Sort: ")
    lines.append("<button class='hn-sort-btn hn-sort-active' data-sort='date'>Date ↓</button>")
    lines.append("<button class='hn-sort-btn' data-sort='score'>Score ↓</button>")
    lines.append("<button class='hn-sort-btn' data-sort='relevance'>Relevance</button>")
    lines.append("</div>")
    lines.append("</div>")
    lines.append("<div id='hn-search-results' class='hn-search-results' style='display:none;'></div>")
    lines.append("<button id='hn-search-more' class='hn-search-more' style='display:none;'>Show more results</button>")

    # Today's Top Stories section
    top_stories = _get_top_stories(base_dir, all_days, n=10)
    if top_stories:
        top_content_date = top_stories[0].get("content_date", "")
        try:
            top_date_label = datetime.strptime(
                top_content_date, "%Y-%m-%d"
            ).strftime("%b %d, %Y")
        except (TypeError, ValueError):
            top_date_label = top_content_date
        scrape_time_display = top_stories[0].get("scrape_time_display", "")
        top_time_label = ""
        if scrape_time_display:
            time_match = re.match(
                r"^(\d{1,2}:\d{2}),\s+.+?\s+\(([^)]+)\)$",
                scrape_time_display,
            )
            if time_match:
                try:
                    time_24h = datetime.strptime(time_match.group(1), "%H:%M")
                    top_time_label = (
                        f"{time_24h.strftime('%I:%M %p').lstrip('0')} "
                        f"{time_match.group(2)}"
                    )
                except ValueError:
                    top_time_label = time_match.group(1)
            else:
                top_time_label = scrape_time_display
        top_datetime_label = " · ".join(
            label for label in (top_date_label, top_time_label) if label
        )
        date_html = (
            f" <time class='hn-section-date' datetime='{top_content_date}'>"
            f"{top_datetime_label}</time>"
            if top_content_date and top_datetime_label
            else ""
        )
        lines.append("<div class='hn-index-section hn-top-stories-section'>")
        daily_url = top_stories[0].get('daily_url', '')
        title_html = (
            f"<a class='hn-section-title-link' href='{daily_url}'>Today's Top Stories</a>"
            if daily_url
            else "Today's Top Stories"
        )
        lines.append(f"<h3 class='hn-section-title'>{title_html} <span class='hn-section-zh'>\u4eca\u65e5\u5934\u6761</span>{date_html} <span class='hn-hot-badge'>\U0001F525 HOT</span></h3>")
        lines.append("<div class='hn-top-stories-list'>")
        for i, story in enumerate(top_stories, 1):
            score = story['score']
            comments = story['descendants']
            title_en = story['title_en']
            title_zh = story['title_zh']
            url = story['url']
            tags = story['tags']
            hn_id = story.get('hn_id', '')
            daily_url = story.get('daily_url', '')

            if daily_url and hn_id:
                story_link = f"{daily_url}#story-{hn_id}"
            else:
                story_link = url

            extra_cls = ' hn-top-story-extra' if i > 5 else ''
            hn_time = story.get('hn_time', 0)
            lines.append(f"<div class='hn-top-story-item{extra_cls}' data-hn-score='{score}' data-hn-time='{hn_time}'>")
            lines.append(f"<span class='hn-top-story-rank'>{i}</span>")
            lines.append(f"<div class='hn-top-story-content'>")
            lines.append(f"<div class='hn-top-story-title'>")
            if story_link:
                lines.append(f"<a class='hn-top-story-title-text' href='{story_link}'>{title_en}</a>")
            else:
                lines.append(f"<span class='hn-top-story-title-text'>{title_en}</span>")
            if url:
                lines.append(f" <a class='hn-top-story-link' href='{url}' target='_blank' title='Read original article'>&#x1F517;</a>")
            lines.append(f"</div>")
            if title_zh:
                lines.append(f"<div class='hn-top-story-zh'>{title_zh}</div>")
            meta_parts = []
            hot_score = story.get('hot_score', 0)
            hot_display = str(round(hot_score)) if hot_score >= 10 else f"{hot_score:.1f}"
            meta_parts.append(f"<span class='hn-hot-idx'>&#128293; {hot_display}</span>")
            meta_parts.append(f"<span class='hn-top-story-score'>&#9650; {score}</span>")
            meta_parts.append(f"<span class='hn-top-story-comments'>&#128172; {comments}</span>")
            for tag in tags[:3]:
                meta_parts.append(f"<span class='hn-top-story-tag'>{tag}</span>")
            lines.append(f"<div class='hn-top-story-meta'>{' '.join(meta_parts)}</div>")
            lines.append(f"</div>")  # hn-top-story-content
            lines.append(f"</div>")  # hn-top-story-item
        if len(top_stories) > 5:
            lines.append("<button class='hn-top-stories-toggle' id='hn-top-stories-toggle'>Show more \u25BC</button>")
        lines.append("</div>")  # hn-top-stories-list
        lines.append("</div>")  # hn-top-stories-section

    # ── News Archive: grouped by ISO week ──
    week_groups = _group_days_by_week(days)

    if not week_groups:
        lines.append("<p class='hn-hint'>No files found yet. Run the workflow once to generate the first file.</p>")
    else:
        lines.append("<div class='hn-index-section hn-archive-section'>")
        lines.append("<h3 class='hn-section-title'>News Archive <span class='hn-section-zh'>\u65b0\u95fb\u5f52\u6863</span></h3>")

        for wg in week_groups:
            iso_week = wg["iso_week"]
            week_label = wg["label"]
            week_days = wg["days"]
            is_current_week = (iso_week == current_week_str)

            # Compute week-level summary
            week_total_stories = 0
            week_day_count = len(week_days)
            for wd in week_days:
                for s in wd.stories:
                    week_total_stories += (s.count_written or 0)

            # Date range for this week
            date_list = sorted([d.content_date for d in week_days])
            try:
                short_dates = [datetime.strptime(value, "%Y-%m-%d").strftime("%m-%d") for value in date_list]
                date_range_str = f"{short_dates[0]} \u2014 {short_dates[-1]}" if len(short_dates) > 1 else short_dates[0]
                week_start_dt = datetime.strptime(date_list[0], "%Y-%m-%d")
                week_end_dt = datetime.strptime(date_list[-1], "%Y-%m-%d")
            except ValueError:
                date_range_str = f"{date_list[0]} \u2014 {date_list[-1]}" if len(date_list) > 1 else date_list[0]
                week_start_dt = week_end_dt = None

            # In the descending archive, place a completed month immediately
            # before the week containing its final day. This visually marks
            # the boundary between the old month and the newer one.
            if week_start_dt and week_end_dt:
                for monthly in monthly_entries:
                    if week_start_dt <= monthly["end_date"] <= week_end_dt:
                        lines.append("<div class='hn-month-divider'>")
                        lines.append(f"<div class='hn-month-heading'>Best of the Month <span>{monthly['label']}</span></div>")
                        lines.append(f"<a class='hn-story-link hn-monthly-digest-link' href='{monthly['url']}'>")
                        lines.append("<span class='hn-row-type hn-type-monthly'>Monthly Top</span>")
                        lines.append(f"<span class='hn-row-detail'>{monthly['detail']}</span>")
                        lines.append("</a>")
                        lines.append("</div>")

            # Check if weekly digest exists
            weekly_entry = weekly_map.get(iso_week)
            # Build summary line for the <summary> header
            summary_parts = [date_range_str]
            if week_total_stories:
                summary_parts.append(f"{week_total_stories} stories")
            summary_parts.append(f"{week_day_count} days")
            if weekly_entry:
                summary_parts.append("\U0001F4CA Weekly Digest")
            summary_meta = ' <span class="hn-row-sep">\u00B7</span> '.join(summary_parts)

            # Use <details> for collapsible; current week open by default
            open_attr = " open" if is_current_week else ""
            this_week_badge = " <span class='hn-this-week-badge'>This Week</span>" if is_current_week else ""

            lines.append(f"<details class='hn-week-group'{open_attr}>")
            lines.append(f"<summary class='hn-week-summary'>")
            lines.append(f"<span class='hn-week-title'>{week_label}{this_week_badge}</span>")
            lines.append(f"<span class='hn-week-meta'>{summary_meta}</span>")
            lines.append(f"</summary>")

            lines.append("<div class='hn-week-content'>")

            # Weekly digest link (if available)
            if weekly_entry:
                lines.append(f"<a class='hn-story-link hn-weekly-digest-link' href='{weekly_entry['url']}'>")
                lines.append(f"<span class='hn-row-type hn-type-weekly'>Weekly Digest</span>")
                lines.append(f"<span class='hn-row-detail'>{weekly_entry['detail']}</span>")
                lines.append("</a>")

            # Daily rows within this week
            lines.append("<div class='hn-grid'>")
            for day in week_days:
                lines.append("<div class='hn-day-row'>")
                try:
                    _dt = datetime.strptime(day.content_date, "%Y-%m-%d")
                    _weekday = _dt.strftime("%a")
                    day_label = _dt.strftime("%m-%d")
                except Exception:
                    _weekday = ""
                    day_label = day.content_date
                weekday_html = f" <span class='hn-day-weekday'>{_weekday}</span>" if _weekday else ""
                lines.append(f"<div class='hn-day-date'>{day_label}{weekday_html}</div>")
                lines.append("<div class='hn-day-stories'>")

                for s in day.stories:
                    if s.story_type == "best":
                        type_label = "Daily Best"
                    elif s.edition in ("morning", "full"):
                        type_label = "Daily Top Stories"
                    else:
                        type_label = "Trending"
                    type_class = "hn-type-best" if s.story_type == "best" else "hn-type-top"
                    detail_html = _build_detail_html(s)

                    lines.append(f"<a class='hn-story-link' href='{s.rel_url}'>")
                    lines.append(f"<span class='hn-row-type {type_class}'>{type_label}</span>")
                    if detail_html:
                        lines.append(f"<span class='hn-row-detail'>{detail_html}</span>")

                    lines.append("</a>")

                lines.append("</div>")  # hn-day-stories
                lines.append("</div>")  # hn-day-row

            lines.append("</div>")  # hn-grid
            lines.append("</div>")  # hn-week-content
            lines.append("</details>")  # hn-week-group

        lines.append("</div>")  # hn-archive-section

    lines.append("")
    lines.append(f"<p class='hn-hint'>Browse by date: <code>/{base_dir}/YYYY/MM/DD/</code></p>")
    lines.append("")

    md = "\n".join(lines)
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md
