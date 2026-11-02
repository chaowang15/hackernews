"""
Tag Cloud Data Builder for Hacker News Daily.

Scans all JSON story files and computes tag frequency statistics,
outputting a compact JSON file for the D3.js word cloud on the index page.

Output: hackernews/tag_cloud.json
"""

import json
import os
import re
from collections import Counter
from typing import Dict, List

JSON_RE = re.compile(r"^(best|top)_stories_(\d{8})\.json$")


def build_tag_cloud(
    base_dir: str = "hackernews",
    output_path: str = "hackernews/tag_cloud.json",
) -> int:
    """
    Scan all JSON files under base_dir, count tag occurrences across
    all unique stories (deduped by HN ID), and write a tag cloud JSON.

    Returns the number of unique tags.
    """
    # Deduplicate stories by HN ID (keep highest score)
    stories: Dict[int, dict] = {}

    for root, _, files in os.walk(base_dir):
        for fn in files:
            m = JSON_RE.match(fn)
            if not m:
                continue

            abs_path = os.path.join(root, fn)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            items = data.get("items", []) or []
            for item in items:
                hn = item.get("hn", {}) or {}
                hn_id = hn.get("id")
                if not hn_id:
                    continue

                score = hn.get("score", 0) or 0
                existing = stories.get(hn_id)
                if existing and existing.get("_score", 0) >= score:
                    continue

                stories[hn_id] = {
                    "_score": score,
                    "tags": item.get("tags", []),
                }

    # Count tag frequencies
    tag_counter: Counter = Counter()
    for s in stories.values():
        tags = s.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    tag_counter[tag.strip()] += 1

    # Build output: sorted by count descending
    tag_list = [
        {"tag": tag, "count": count}
        for tag, count in tag_counter.most_common()
    ]

    output = {
        "total_stories": len(stories),
        "total_tags": len(tag_list),
        "tags": tag_list,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"[TAG CLOUD] Written {len(tag_list)} tags from {len(stories)} stories to {output_path} ({size_kb:.1f} KB)")
    return len(tag_list)
