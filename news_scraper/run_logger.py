"""
Scrape run logger: records every pipeline execution to a Markdown log file.

Each run is logged with:
- Timestamp (PST), trigger type (schedule / manual / local)
- Mode (top / best / all), duration
- Items: total, new (LLM), reused (same-day), reused (cross-day)
- Token usage and estimated cost for the run

Log file: logs/scrape_run_log.md
"""

import os
from datetime import datetime, timezone, timedelta

PST = timezone(timedelta(hours=-8))

TABLE_HEADER = (
    "| Time (PST) | Trigger | Mode | Duration | Total Items "
    "| New (LLM) | Reused (same-day) | Reused (cross-day) "
    "| Tokens | Cost (USD) | Note |\n"
    "|------------|---------|------|----------|------------:"
    "|----------:|------------------:|-------------------:"
    "|------:|-----------:|------|\n"
)


def _get_log_path() -> str:
    """Return the absolute path to the scrape run log file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "scrape_run_log.md")


def _get_today_str() -> str:
    return datetime.now(PST).strftime("%Y-%m-%d")


def log_scrape_run(
    mode: str,
    trigger: str,
    duration_sec: float,
    total_items: int,
    new_llm: int,
    reused_same_day: int,
    reused_cross_day: int,
    total_tokens: int = 0,
    total_cost: float = 0.0,
    note: str = "",
) -> None:
    """
    Append a scrape run record to the log file.

    Parameters:
        mode: "top", "best", or "all"
        trigger: "schedule", "manual" (workflow_dispatch), or "local"
        duration_sec: Pipeline wall-clock time in seconds
        total_items: Total items in the final JSON
        new_llm: Number of items that required LLM enrichment
        reused_same_day: Items reused from today's existing JSON
        reused_cross_day: Items reused from previous day's JSON
        total_tokens: Total LLM tokens used in this run
        total_cost: Total estimated LLM cost in USD
        note: Optional note
    """
    log_path = _get_log_path()
    today = _get_today_str()
    now_pst = datetime.now(PST)
    time_str = now_pst.strftime("%H:%M:%S")

    file_exists = os.path.exists(log_path)
    today_section_exists = False

    if file_exists:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        today_section_exists = f"## {today}" in content

    duration_str = f"{duration_sec:.0f}s"
    cost_str = f"${total_cost:.4f}" if total_cost > 0 else "—"
    tokens_str = f"{total_tokens:,}" if total_tokens > 0 else "—"
    note_clean = note.replace("|", "/") if note else ""

    with open(log_path, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("# Scrape Run Log\n\n")
            f.write("This file tracks every pipeline execution of the Hacker News Daily scraper.\n")
            f.write("Each row records one `run_scrape()` invocation.\n\n")
            f.write("---\n\n")

        if not today_section_exists:
            f.write(f"## {today}\n\n")
            f.write(TABLE_HEADER)

        f.write(
            f"| {time_str} "
            f"| {trigger} "
            f"| {mode} "
            f"| {duration_str} "
            f"| {total_items} "
            f"| {new_llm} "
            f"| {reused_same_day} "
            f"| {reused_cross_day} "
            f"| {tokens_str} "
            f"| {cost_str} "
            f"| {note_clean} |\n"
        )

    print(
        f"[RUN LOG] {time_str} PST | {trigger} | mode={mode} | "
        f"{duration_str} | items={total_items} (new={new_llm}, "
        f"same_day={reused_same_day}, cross_day={reused_cross_day}) | "
        f"tokens={tokens_str} | cost={cost_str}"
    )
