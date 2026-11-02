"""
Tag Trend Data Builder for Hacker News Daily.

Scans all JSON story files and computes per-day tag frequency,
outputting a compact JSON file for the Streamgraph on the index page.

Output: hackernews/tag_trend.json
"""

import json
import os
import re
from collections import Counter, defaultdict
from typing import Dict, List

JSON_RE = re.compile(r"^(best|top)_stories_(\d{8})\.json$")

# Top N tags to include in the stream chart (no "Other" bucket)
TOP_N_TAGS = 20


def build_tag_trend(
    base_dir: str = "hackernews",
    output_path: str = "hackernews/tag_trend.json",
    top_n: int = TOP_N_TAGS,
) -> int:
    """
    Scan all JSON files under base_dir, compute per-day tag frequencies
    (deduped by HN ID within each day), and write a trend JSON.

    Returns the number of dates.
    """
    # date -> {hn_id: {score, tags}}
    day_stories: Dict[str, Dict[int, dict]] = defaultdict(dict)

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

            meta = data.get("meta", {}) or {}
            content_date = meta.get("content_date", "")
            if not content_date:
                continue

            for item in data.get("items", []) or []:
                hn = item.get("hn", {}) or {}
                hn_id = hn.get("id")
                if not hn_id:
                    continue

                score = hn.get("score", 0) or 0
                existing = day_stories[content_date].get(hn_id)
                if existing and existing["score"] >= score:
                    continue

                day_stories[content_date][hn_id] = {
                    "score": score,
                    "tags": item.get("tags", []),
                }

    if not day_stories:
        print("[TAG TREND] No data found.")
        return 0

    # Compute global tag ranking to pick top N
    global_counter: Counter = Counter()
    for date, stories in day_stories.items():
        for s in stories.values():
            tags = s.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and tag.strip():
                        global_counter[tag.strip()] += 1

    top_tags = [tag for tag, _ in global_counter.most_common(top_n)]

    # Build per-day series
    sorted_dates = sorted(day_stories.keys())
    series: List[dict] = []

    for date in sorted_dates:
        day_counter: Counter = Counter()
        for s in day_stories[date].values():
            tags = s.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and tag.strip():
                        day_counter[tag.strip()] += 1

        entry = {"date": date}
        for tag in top_tags:
            entry[tag] = day_counter.get(tag, 0)

        series.append(entry)

    output = {
        "tags": top_tags,
        "series": series,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(
        f"[TAG TREND] Written {len(sorted_dates)} days × {len(top_tags)} tags "
        f"to {output_path} ({size_kb:.1f} KB)"
    )
    return len(sorted_dates)
