"""
Re-summarize: regenerate summary_en, summary_zh, and title_zh for all items
in existing JSON backup files using the improved LLM prompt.

This script does NOT call the HN API. It reads title_en and url from the
existing JSON, sends them to the LLM, and overwrites the summary fields.

Usage:
  python news_scraper/resummarize.py                    # re-summarize all JSON files
  python news_scraper/resummarize.py <path.json>        # re-summarize one file
"""

import glob
import json
import os
import sys
from typing import Dict, List

from llm_batch import llm_enrich_batch


def resummarize_json_file(json_path: str, model: str = "gpt-4.1-mini") -> bool:
    """
    Read a backup JSON, re-generate summaries for all items, write back.
    Returns True if summaries were updated.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    if not items:
        print(f"  [SKIP] No items in {json_path}")
        return False

    # Prepare input for LLM (only needs id, title_en, url)
    llm_input = []
    for it in items:
        item_id = it.get("hn", {}).get("id", 0)
        llm_input.append({
            "id": item_id,
            "title_en": it.get("title_en", ""),
            "url": it.get("url", ""),
        })

    print(f"  [RESUMMARIZE] Generating new summaries for {len(items)} items in {json_path} ...")

    # Process in batches of 25 to avoid output truncation
    BATCH_SIZE = 25
    enriched = {}
    for batch_start in range(0, len(llm_input), BATCH_SIZE):
        batch = llm_input[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(llm_input) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"    Batch {batch_num}/{total_batches}: {len(batch)} items ...")
        batch_result = llm_enrich_batch(batch, model=model)
        enriched.update(batch_result)

    updated = 0
    for it in items:
        item_id = int(it.get("hn", {}).get("id", 0))
        if item_id in enriched:
            it["title_zh"] = enriched[item_id]["title_zh"]
            it["summary_en"] = enriched[item_id]["summary_en"]
            it["summary_zh"] = enriched[item_id]["summary_zh"]
            updated += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  [DONE] Updated {updated}/{len(items)} items in {json_path}")
    return True


def resummarize_all(base_dir: str = "hackernews", model: str = "gpt-4.1-mini"):
    """Re-summarize all JSON backup files under base_dir."""
    pattern = os.path.join(base_dir, "*", "*", "*", "best_stories_*.json")
    json_paths = sorted(glob.glob(pattern))

    if not json_paths:
        print(f"[RESUMMARIZE] No JSON files found under {pattern}")
        return

    print(f"[RESUMMARIZE] Found {len(json_paths)} JSON files. Processing...")
    for jp in json_paths:
        try:
            resummarize_json_file(jp, model=model)
        except Exception as e:
            print(f"  [ERROR] Failed for {jp}: {e}")

    print("[RESUMMARIZE] All done.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        resummarize_json_file(path)
    else:
        resummarize_all()
