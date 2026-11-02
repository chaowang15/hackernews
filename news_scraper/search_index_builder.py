"""
Build a lightweight search_index.json from all HN story JSON files.

The index contains one entry per unique story (deduped by HN ID),
with fields optimized for client-side Fuse.js search.
"""

import os
import json
import re
from typing import Dict, List, Optional

JSON_RE = re.compile(r"^(best|top)_stories_(\d{8})\.json$")


def build_search_index(
    base_dir: str = "hackernews",
    output_path: str = "hackernews/search_index.json",
) -> int:
    """
    Scan all JSON files under base_dir, extract story items,
    deduplicate by HN ID (keeping the highest score), and write
    a compact search index JSON.

    Returns the number of unique stories indexed.
    """
    # hn_id -> best record (keep highest score)
    stories: Dict[int, dict] = {}

    for root, _, files in os.walk(base_dir):
        for fn in files:
            m = JSON_RE.match(fn)
            if not m:
                continue

            story_type = m.group(1)  # "best" or "top"
            abs_path = os.path.join(root, fn)

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            meta = data.get("meta", {}) or {}
            items = data.get("items", []) or []
            content_date = meta.get("content_date", "")

            # Build the page URL for linking
            rel_dir = os.path.relpath(root, base_dir).replace("\\", "/")
            page_url = f"/{base_dir}/{rel_dir}/{fn[:-5]}"  # strip .json

            for item in items:
                hn = item.get("hn", {}) or {}
                hn_id = hn.get("id")
                if not hn_id:
                    continue

                score = hn.get("score", 0) or 0
                existing = stories.get(hn_id)

                # Keep the entry with the highest score
                if existing and existing.get("score", 0) >= score:
                    continue

                entry = {
                    "id": hn_id,
                    "t": item.get("title_en", ""),        # title English
                    "z": item.get("title_zh", ""),        # title Chinese
                    "u": item.get("url", ""),             # original URL
                    "tags": item.get("tags", []),
                    "score": score,
                    "date": content_date,
                    "type": story_type,                   # "best" or "top"
                    "page": page_url,                     # link to our page
                    "by": hn.get("by", ""),
                    "comments": hn.get("descendants", 0) or 0,
                    "hn_url": hn.get("comments_url", ""),
                }

                stories[hn_id] = entry

    # Sort by score descending
    sorted_stories = sorted(stories.values(), key=lambda x: x.get("score", 0), reverse=True)

    # Write compact JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_stories, f, ensure_ascii=False, separators=(",", ":"))

    count = len(sorted_stories)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"[SEARCH INDEX] Written {count} unique stories to {output_path} ({size_kb:.1f} KB)")
    return count
