"""
share_page_builder.py — Generate per-story redirect pages with Open Graph meta tags.

Each story gets a tiny HTML file at hackernews/share/{story_id}.html that:
  1. Contains OG meta tags (title, description, image) for rich link previews
  2. Immediately redirects to the daily page anchor (#story-{id})

This enables rich previews when sharing story links on Line, Slack, Twitter, etc.
"""

import json
import os
import html
import glob
import logging

logger = logging.getLogger(__name__)

SITE_BASE = "https://chaowang15.github.io"
SHARE_DIR = "hackernews/share"

# HTML template for redirect pages
SHARE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Hacker News Daily">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<meta property="og:url" content="{og_url}">
{og_image_tag}<meta name="twitter:card" content="{twitter_card}">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_description}">
{twitter_image_tag}<meta http-equiv="refresh" content="0;url={redirect_url}">
<title>{page_title}</title>
</head>
<body>
<p>Redirecting to <a href="{redirect_url}">{page_title}</a>...</p>
</body>
</html>
"""


def _escape(text):
    """Escape text for use in HTML attributes."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def _truncate(text, max_len=200):
    """Truncate text to max_len characters."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 3].rsplit(" ", 1)[0] + "..."


def _build_description(story):
    """Build OG description from story summary (bilingual)."""
    en = story.get("summary_en", "").strip()
    zh = story.get("summary_zh", "").strip()
    
    # Prefer bilingual, fall back to whichever is available
    if en and zh:
        desc = _truncate(en, 120) + " — " + _truncate(zh, 80)
    elif en:
        desc = _truncate(en, 200)
    elif zh:
        desc = _truncate(zh, 200)
    else:
        desc = story.get("title_en", "")
    
    # Add tags if available
    tags = story.get("tags", [])
    if tags:
        desc += " | " + ", ".join(tags[:5])
    
    return desc


def _get_page_url(meta):
    """Get the daily page URL from meta info."""
    date_dir = meta.get("date_dir", "")
    content_date = meta.get("content_date", "")
    mode = meta.get("mode", "top")
    
    if mode == "top":
        filename = f"top_stories_{content_date.replace('-', '')[4:]}{content_date[:4]}"
    else:
        filename = f"best_stories_{content_date.replace('-', '')[4:]}{content_date[:4]}"
    
    return f"/hackernews/{date_dir}/{filename}"


def generate_share_page(story, meta, repo_root):
    """Generate a single share page HTML file for a story.
    
    Returns the relative share URL path (e.g., /hackernews/share/47091419.html)
    """
    story_id = story.get("hn", {}).get("id")
    if not story_id:
        return None
    
    title_en = story.get("title_en", "Untitled")
    title_zh = story.get("title_zh", "")
    
    # Build OG title (bilingual)
    if title_zh:
        og_title = f"{title_en} | {title_zh}"
    else:
        og_title = title_en
    
    # Truncate OG title if too long
    og_title = _truncate(og_title, 120)
    
    # Build description
    og_description = _build_description(story)
    
    # Image
    image_url = story.get("image_url", "")
    if image_url and not image_url.startswith("http"):
        image_url = ""  # Skip invalid URLs
    
    og_image_tag = ""
    twitter_image_tag = ""
    twitter_card = "summary"
    if image_url:
        og_image_tag = f'<meta property="og:image" content="{_escape(image_url)}">\n'
        twitter_image_tag = f'<meta name="twitter:image" content="{_escape(image_url)}">\n'
        twitter_card = "summary_large_image"
    
    # URLs
    page_url = _get_page_url(meta)
    redirect_url = f"{page_url}#story-{story_id}"
    share_url = f"/hackernews/share/{story_id}.html"
    og_url = f"{SITE_BASE}{share_url}"
    
    # Page title
    page_title = _escape(title_en)
    
    # Render template
    html_content = SHARE_PAGE_TEMPLATE.format(
        og_title=_escape(og_title),
        og_description=_escape(og_description),
        og_url=_escape(og_url),
        og_image_tag=og_image_tag,
        twitter_card=twitter_card,
        twitter_image_tag=twitter_image_tag,
        redirect_url=redirect_url,
        page_title=page_title,
    )
    
    # Write file
    share_dir = os.path.join(repo_root, SHARE_DIR)
    os.makedirs(share_dir, exist_ok=True)
    
    filepath = os.path.join(share_dir, f"{story_id}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return share_url


def build_share_pages(repo_root):
    """Generate share pages for all stories in all JSON files.
    
    Scans all daily JSON files and generates a redirect page for each story.
    Returns the total number of share pages generated.
    """
    json_pattern = os.path.join(repo_root, "hackernews/2026/**/*.json")
    json_files = glob.glob(json_pattern, recursive=True)
    
    # Also include weekly digest JSON
    weekly_pattern = os.path.join(repo_root, "hackernews/weekly/*.json")
    weekly_files = glob.glob(weekly_pattern)
    
    total = 0
    seen_ids = set()
    
    # Process daily JSONs
    for jf in sorted(json_files):
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            meta = data.get("meta", {})
            items = data.get("items", [])
            
            for story in items:
                story_id = story.get("hn", {}).get("id")
                if not story_id or story_id in seen_ids:
                    continue
                seen_ids.add(story_id)
                
                result = generate_share_page(story, meta, repo_root)
                if result:
                    total += 1
        except Exception as e:
            logger.warning(f"Error processing {jf}: {e}")
    
    # Process weekly JSONs — stories in weekly may point to different daily pages
    # Weekly stories already exist in daily JSONs, so we skip duplicates via seen_ids
    for wf in sorted(weekly_files):
        try:
            with open(wf, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", [])
            for story in items:
                story_id = story.get("hn", {}).get("id")
                if not story_id or story_id in seen_ids:
                    continue
                seen_ids.add(story_id)
                
                # For weekly, we need to find the correct daily page
                # Use the story's source_date if available
                source_meta = story.get("_source_meta", {})
                if not source_meta:
                    # Build meta from story info
                    source_meta = {
                        "mode": story.get("_source_type", "top"),
                        "date_dir": story.get("_source_date_dir", ""),
                        "content_date": story.get("_source_content_date", ""),
                    }
                
                if source_meta.get("date_dir"):
                    result = generate_share_page(story, source_meta, repo_root)
                    if result:
                        total += 1
        except Exception as e:
            logger.warning(f"Error processing {wf}: {e}")
    
    logger.info(f"Generated {total} share pages in {SHARE_DIR}/")
    return total


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    total = build_share_pages(repo_root)
    print(f"Generated {total} share pages")
