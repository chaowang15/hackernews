"""
RSS/Atom Feed Builder for Hacker News Daily.

Generates an RSS 2.0 feed from the latest daily JSON story files.
The feed includes the most recent stories across all available days,
sorted by HN score descending.

Output: hackernews/feed.xml
"""

import json
import os
import re
import glob
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


SITE_URL = "https://chaowang15.github.io"
FEED_TITLE = "Hacker News Daily"
FEED_DESCRIPTION = (
    "Curated daily digest of top Hacker News stories with AI-generated "
    "summaries, tags, and bilingual translations."
)
FEED_LANGUAGE = "en-us"
MAX_ITEMS = 50  # Max items in the feed
MAX_DAYS = 7    # Look back at most N days

JSON_RE = re.compile(r"^(best|top)_stories_(\d{8})\.json$")


def _rfc822(dt: datetime) -> str:
    """Format datetime as RFC 822 for RSS pubDate."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _iso8601(dt: datetime) -> str:
    """Format datetime as ISO 8601 for Atom."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _escape_cdata(text: str) -> str:
    """Wrap text in CDATA for safe XML embedding."""
    return f"<![CDATA[{text}]]>"


def build_rss_feed(
    base_dir: str = "hackernews",
    output_path: str = "hackernews/feed.xml",
    max_items: int = MAX_ITEMS,
    max_days: int = MAX_DAYS,
) -> int:
    """
    Scan recent JSON files, collect stories, deduplicate by HN ID
    (keeping highest score), and write an RSS 2.0 feed.

    Returns the number of items written.
    """
    # Collect all JSON files
    json_files = sorted(
        glob.glob(os.path.join(base_dir, "2*/*/*/*.json")),
        reverse=True,
    )

    # Deduplicate stories by HN ID, keeping highest score
    seen_ids = {}  # hn_id -> story dict
    dates_seen = set()

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        meta = data.get("meta", {}) or {}
        content_date = meta.get("content_date", "")
        if not content_date:
            continue

        dates_seen.add(content_date)
        if len(dates_seen) > max_days:
            break

        mode = meta.get("mode", "")
        for item in data.get("items", []) or []:
            hn = item.get("hn", {}) or {}
            hn_id = hn.get("id")
            if not hn_id:
                continue

            score = hn.get("score", 0) or 0
            existing = seen_ids.get(hn_id)
            if existing and existing["score"] >= score:
                continue

            # Build the page URL for this story
            # Trending page: /hackernews/YYYY/MM/DD/top_stories_MMDDYYYY
            date_parts = content_date.split("-")
            if len(date_parts) == 3:
                y, m, d = date_parts
                page_slug = f"top_stories_{m}{d}{y}"
                page_url = f"{SITE_URL}/{base_dir}/{y}/{m}/{d}/{page_slug}"
            else:
                page_url = SITE_URL

            seen_ids[hn_id] = {
                "hn_id": hn_id,
                "title": item.get("title_en", "Untitled"),
                "url": item.get("url", ""),
                "summary": item.get("summary_en", ""),
                "summary_zh": item.get("summary_zh", ""),
                "tags": item.get("tags", []),
                "score": score,
                "comments": hn.get("descendants", 0) or 0,
                "comments_url": hn.get("comments_url", ""),
                "author": hn.get("by", ""),
                "time": hn.get("time", 0),
                "content_date": content_date,
                "page_url": page_url,
                "mode": mode,
            }

    if not seen_ids:
        print("[RSS] No stories found.")
        return 0

    # Sort by score descending, take top N
    stories = sorted(seen_ids.values(), key=lambda x: x["score"], reverse=True)
    stories = stories[:max_items]

    # Build RSS XML
    now = datetime.now(timezone.utc)

    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")

    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = FEED_TITLE
    SubElement(channel, "link").text = f"{SITE_URL}/{base_dir}/"
    SubElement(channel, "description").text = FEED_DESCRIPTION
    SubElement(channel, "language").text = FEED_LANGUAGE
    SubElement(channel, "lastBuildDate").text = _rfc822(now)
    SubElement(channel, "generator").text = "Hacker News Daily RSS Builder"

    # Atom self-link
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", f"{SITE_URL}/{base_dir}/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for story in stories:
        item_el = SubElement(channel, "item")

        SubElement(item_el, "title").text = story["title"]

        # Link to original article
        link_url = story["url"] or story["comments_url"]
        SubElement(item_el, "link").text = link_url

        # GUID: use HN item URL for uniqueness
        guid = SubElement(item_el, "guid")
        guid.text = story["comments_url"] or f"hn-{story['hn_id']}"
        guid.set("isPermaLink", "true" if story["comments_url"] else "false")

        # Author
        if story["author"]:
            SubElement(item_el, "dc:creator").text = story["author"]

        # Publication date from HN timestamp
        if story["time"]:
            pub_dt = datetime.fromtimestamp(story["time"], tz=timezone.utc)
            SubElement(item_el, "pubDate").text = _rfc822(pub_dt)

        # Categories (tags)
        for tag in story.get("tags", []):
            if isinstance(tag, str) and tag.strip():
                SubElement(item_el, "category").text = tag.strip()

        # Description: summary + metadata
        desc_parts = []
        if story["summary"]:
            desc_parts.append(f"<p>{story['summary']}</p>")
        if story["summary_zh"]:
            desc_parts.append(f"<p><em>{story['summary_zh']}</em></p>")

        meta_line = f"▲ {story['score']} · 💬 {story['comments']}"
        if story["tags"]:
            meta_line += " · " + " · ".join(story["tags"])
        desc_parts.append(f"<p><small>{meta_line}</small></p>")

        # Links to HN discussion and daily page
        links = []
        if story["comments_url"]:
            links.append(
                f'<a href="{story["comments_url"]}">HN Discussion</a>'
            )
        links.append(
            f'<a href="{story["page_url"]}#story-{story["hn_id"]}">View on Hacker News Daily</a>'
        )
        desc_parts.append(f"<p>{' · '.join(links)}</p>")

        SubElement(item_el, "description").text = "\n".join(desc_parts)

    # Write XML
    rough_string = tostring(rss, encoding="unicode", xml_declaration=False)
    xml_string = f'<?xml version="1.0" encoding="UTF-8"?>\n{rough_string}'

    # Pretty print
    try:
        dom = minidom.parseString(xml_string)
        xml_string = dom.toprettyxml(indent="  ", encoding=None)
        # Remove extra xml declaration from toprettyxml
        if isinstance(xml_string, str):
            lines = xml_string.split("\n")
        else:
            lines = xml_string.decode("utf-8").split("\n")
        # Keep only one xml declaration
        result_lines = []
        seen_decl = False
        for line in lines:
            if line.strip().startswith("<?xml"):
                if not seen_decl:
                    seen_decl = True
                    result_lines.append(line)
            else:
                result_lines.append(line)
        xml_string = "\n".join(result_lines)
    except Exception:
        pass  # Fall back to non-pretty output

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_string)

    size_kb = os.path.getsize(output_path) / 1024
    print(
        f"[RSS] Written {len(stories)} items from {len(dates_seen)} days "
        f"to {output_path} ({size_kb:.1f} KB)"
    )
    return len(stories)
