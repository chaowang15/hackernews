from typing import List, Dict, Optional
import re
from datetime import datetime, timedelta

# Tag color mapping: each tag gets a distinct hue for visual differentiation.
# Colors are defined as CSS class suffixes; actual colors are in hn.css.
TAG_COLOR_MAP = {
    "AI":            "blue",
    "Programming":   "indigo",
    "Security":      "red",
    "Science":       "teal",
    "Business":      "amber",
    "Finance":       "amber",
    "Hardware":      "slate",
    "Open Source":   "green",
    "Design":        "pink",
    "Web":           "cyan",
    "DevOps":        "indigo",
    "Data":          "violet",
    "Gaming":        "purple",
    "Entertainment": "purple",
    "Politics":      "orange",
    "Health":        "emerald",
    "Education":     "sky",
    "Career":        "sky",
    "Privacy":       "red",
    "Legal":         "orange",
    "Culture":       "rose",
    "Space":         "teal",
    "Energy":        "emerald",
    "Startups":      "amber",
    "Show HN":       "green",
}


def _tag_html(tag: str) -> str:
    """Render a single tag as an inline badge with color class and data attribute."""
    color = TAG_COLOR_MAP.get(tag, "slate")
    safe_tag = tag.replace('"', '&quot;')
    return f"<span class='hn-tag hn-tag--{color}' data-tag='{safe_tag}'>{tag}</span>"


def _detect_mode(page_title: str) -> str:
    """Detect story mode from page title string."""
    if "Trending" in page_title or "Daily Top Stories" in page_title:
        return "top"
    return "best"


def render_markdown(
    items: List[Dict],
    page_title: str,
    page_subtitle: str = "",
    html_title: Optional[str] = None,
) -> str:
    """
    New version:
    - layout: hn (handled by _layouts/hn.html)
    - No inline <style> or <script> (layout includes /assets/hn/hn.css + hn.js)
    Note: main.py will additionally clean legacy head tags / wrap if present.
    """
    fm_title = html_title or page_title
    mode = _detect_mode(page_title)

    lines = []
    lines.append("---")
    lines.append("layout: hn")
    lines.append(f'title: "{fm_title}"')
    lines.append("---")
    lines.append("")

    # Header with mode badge
    if mode == "top":
        if "Morning 50" in page_title:
            badge_text = "Daily Top Stories · Morning 50"
        elif "All 100" in page_title:
            badge_text = "Daily Top Stories · All 100"
        else:
            badge_text = "Trending"
        badge = f"<span class='hn-mode-badge hn-mode-top'>{badge_text}</span>"
    else:
        badge = "<span class='hn-mode-badge hn-mode-best'>Daily Best</span>"

    # Extract the date portion for a cleaner H1
    # page_title: "Hacker News — Daily Best (2026-02-18)" or "Hacker News — Trending (2026-02-19)"
    m_date = re.search(r"\((\d{4}-\d{2}-\d{2})\)", page_title)
    date_str = m_date.group(1) if m_date else ""

    if date_str:
        h1_text = f"Hacker News Daily — {date_str}"
    else:
        h1_text = "Hacker News Daily"

    lines.append(f"<h1 class='hn-h1'>{h1_text} {badge}</h1>")

    # Prev / Index / Next navigation
    prev_href = None
    next_href = None
    file_prefix = "top_stories" if mode == "top" else "best_stories"

    if m_date:
        try:
            dt = datetime.strptime(m_date.group(1), "%Y-%m-%d")

            prev_dt = dt - timedelta(days=1)
            next_dt = dt + timedelta(days=1)

            prev_href = (
                f"/hackernews/{prev_dt.strftime('%Y/%m/%d')}/"
                f"{file_prefix}_{prev_dt.strftime('%m%d%Y')}"
            )
            next_href = (
                f"/hackernews/{next_dt.strftime('%Y/%m/%d')}/"
                f"{file_prefix}_{next_dt.strftime('%m%d%Y')}"
            )
        except Exception:
            prev_href = None
            next_href = None

    # Build Prev/Index/Next nav with pill button styling
    nav_html = "<div class='hn-nav'>"

    if prev_href:
        nav_html += f"<a class='hn-nav-btn hn-prev' href='{prev_href}'>‹ Prev day</a>"
    else:
        nav_html += "<span></span>"

    nav_html += "<a class='hn-nav-btn hn-nav-index' href='/hackernews/'>← Index</a>"

    if next_href:
        nav_html += f"<a class='hn-nav-btn hn-next' href='{next_href}'>Next day ›</a>"
    else:
        nav_html += "<span></span>"

    nav_html += "</div>"
    lines.append(nav_html)

    subtitle = page_subtitle.strip()
    if subtitle:
        lines.append(f"<p class='hn-subtitle'>{subtitle}</p>")

    lines.append("<hr class='hn-rule'/>")
    lines.append("<div class='hn-list'>")

    for i, it in enumerate(items, start=1):
        title_en: str = it["title_en"]
        url: str = it["url"]
        title_zh: str = it.get("title_zh", "")
        summary_en: str = it.get("summary_en", "")
        summary_zh: str = it.get("summary_zh", "")
        image_url: Optional[str] = it.get("image_url")
        tags: List[str] = it.get("tags", [])
        new_badge = (
            " <span class='hn-new-badge' title='New in this update' "
            "aria-label='New in this update'>NEW</span>"
            if it.get("is_new") else ""
        )

        # Build data-tags attribute for future JS filtering
        tags_data = ",".join(tags) if tags else ""

        # Anchor ID from HN story ID for deep linking
        hn = it.get("hn") or {}
        hn_id = hn.get("id", "")
        id_attr = f" id='story-{hn_id}'" if hn_id else ""
        details_id = f"card-details-{hn_id or i}"

        # Data attributes for JS sorting (hot/top/new)
        hn_time = hn.get("time", "")
        hn_score_val = hn.get("score", 0)
        hot_score_val = it.get("hot_score", 0)
        data_attrs = f" data-hn-time='{hn_time}' data-hn-score='{hn_score_val}' data-hot-score='{hot_score_val}'"

        lines.append(f"<div class='hn-card hn-card-compact hn-no-collapse'{id_attr} data-tags='{tags_data}'{data_attrs}>")
        lines.append("<div class='hn-body'>")
        lines.append(
            f"<div class='hn-digest-summary-header' role='button' tabindex='0' "
            f"aria-expanded='true' aria-controls='{details_id}' "
            "aria-label='Hide summary and image'>"
        )

        lines.append(
            f"<p class='hn-title'>({i}) "
            f"<a href='{url}' target='_blank' rel='noopener noreferrer'>{title_en}</a>"
            f"{new_badge}"
            f"</p>"
        )

        # Chinese subtitle line
        if title_zh:
            lines.append(f"<p class='hn-meta'>{title_zh}</p>")

        # Info row under Chinese subtitle (author and time)
        created_display = it.get("created_display", "")
        hn_score = hn.get("score")
        hn_by = hn.get("by")
        comments_url = hn.get("comments_url")
        hn_desc = hn.get("descendants")

        # Only show the time row if created_display exists
        if created_display:
            lines.append(f"<p class='hn-meta2'><span class='hn-meta2-created'>{created_display}</span></p>")

        # Tags row with score/comments icons (rendered as colored pill badges)
        tag_line_parts = []
        # Score icon (linked to HN comments page)
        if hn_score is not None:
            if comments_url:
                tag_line_parts.append(
                    f"<a class='hn-stat hn-stat-score' href='{comments_url}' target='_blank' rel='noopener noreferrer'>&#9650; {hn_score}</a>"
                )
            else:
                tag_line_parts.append(f"<span class='hn-stat hn-stat-score'>&#9650; {hn_score}</span>")
        # Comments icon (with link to HN comments)
        if hn_desc is not None:
            if comments_url:
                tag_line_parts.append(
                    f"<a class='hn-stat hn-stat-comments' href='{comments_url}' target='_blank' rel='noopener noreferrer'>&#128172; {hn_desc}</a>"
                )
            else:
                tag_line_parts.append(f"<span class='hn-stat hn-stat-comments'>&#128172; {hn_desc}</span>")
        # Tag badges
        for t in tags:
            tag_line_parts.append(_tag_html(t))
        if tag_line_parts:
            lines.append(f"<div class='hn-tags'>{' '.join(tag_line_parts)}</div>")

        lines.append("</div>")
        lines.append(f"<div class='hn-digest-details' id='{details_id}'>")

        if summary_en:
            lines.append(f"<p class='hn-text-en hn-digest-summary'>{summary_en}</p>")
        if summary_zh:
            lines.append(f"<p class='hn-text-zh hn-digest-summary'>{summary_zh}</p>")

        # Reuse the same expanded details order and image style as digests.
        if image_url:
            lines.append(
                f"<img class='hn-img hn-digest-img' src='{image_url}' data-full='{image_url}' "
                f"alt='preview image' loading='lazy' decoding='async'/>"
            )

        lines.append("</div>")  # hn-digest-details
        lines.append("</div>")  # hn-body
        lines.append("</div>")  # hn-card

    lines.append("</div>")  # hn-list
    lines.append("")
    return "\n".join(lines)
