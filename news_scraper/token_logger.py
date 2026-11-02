"""
Token usage logger: tracks OpenAI API token consumption and estimated cost.

Records every LLM call to a Markdown log file with:
- Timestamp, model, caller function
- Input/output/cached token counts
- Estimated cost based on current pricing
- Running daily and cumulative totals

Log file: logs/openai_token_usage_log.md
"""

import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Pricing table (USD per 1M tokens, Standard tier)
# Source: https://developers.openai.com/api/docs/pricing/
# Last updated: 2026-10-31
# ---------------------------------------------------------------------------

PRICING = {
    # model: (input_per_1M, cached_input_per_1M, output_per_1M)
    "gpt-5.6-luna": (0.20,  0.02,   1.20),
    "gpt-5-nano":    (0.05,  0.005,  0.40),
    "gpt-5-mini":    (0.25,  0.025,  2.00),
    "gpt-5":         (1.25,  0.125, 10.00),
    "gpt-5.1":       (1.25,  0.125, 10.00),
    "gpt-5.2":       (1.75,  0.175, 14.00),
    "gpt-4.1-nano":  (0.10,  0.025,  0.40),
    "gpt-4.1-mini":  (0.40,  0.10,   1.60),
    "gpt-4.1":       (2.00,  0.50,   8.00),
    "gpt-4o":        (2.50,  1.25,  10.00),
    "gpt-4o-mini":   (0.15,  0.075,  0.60),
    "gemini-2.5-flash": (0.15, 0.0375, 0.60),  # estimate
}

# ---------------------------------------------------------------------------
# PST timezone
# ---------------------------------------------------------------------------

PST = timezone(timedelta(hours=-8))

# ---------------------------------------------------------------------------
# Session accumulator — tracks totals for the current pipeline run
# ---------------------------------------------------------------------------

_session_tokens = 0
_session_cost = 0.0
_session_calls = 0


def reset_session_stats() -> None:
    """Reset the session accumulator (call at the start of each run_scrape)."""
    global _session_tokens, _session_cost, _session_calls
    _session_tokens = 0
    _session_cost = 0.0
    _session_calls = 0


def get_session_stats() -> dict:
    """Return accumulated token/cost stats for the current session."""
    return {
        "total_tokens": _session_tokens,
        "total_cost": _session_cost,
        "total_calls": _session_calls,
    }


# ---------------------------------------------------------------------------
# Resolve log file path (relative to repo root)
# ---------------------------------------------------------------------------

def _get_log_path() -> str:
    """Return the absolute path to the token usage log file."""
    # Try to find the repo root by looking for the logs/ directory
    # relative to this script's location (news_scraper/ -> repo root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "openai_token_usage_log.md")


def _get_today_str() -> str:
    """Return today's date string in PST."""
    return datetime.now(PST).strftime("%Y-%m-%d")


def _get_timestamp() -> str:
    """Return current timestamp in PST."""
    return datetime.now(PST).strftime("%Y-%m-%d %H:%M:%S PST")


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """
    Estimate the cost of an API call in USD.
    Returns cost rounded to 6 decimal places.
    """
    pricing = PRICING.get(model)
    if pricing is None:
        # Try prefix matching for versioned model names
        for key in PRICING:
            if model.startswith(key):
                pricing = PRICING[key]
                break
    if pricing is None:
        # Unknown model, use gpt-4.1-mini as a safe default
        pricing = PRICING["gpt-4.1-mini"]

    input_price, cached_price, output_price = pricing

    # Non-cached input tokens = total input - cached
    fresh_input = max(0, input_tokens - cached_tokens)

    cost = (
        fresh_input * input_price / 1_000_000
        + cached_tokens * cached_price / 1_000_000
        + output_tokens * output_price / 1_000_000
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Log writing
# ---------------------------------------------------------------------------

def log_token_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    caller: str = "",
    note: str = "",
) -> float:
    """
    Append a token usage record to the log file.

    Parameters:
        model: Model name (e.g., "gpt-5-nano")
        input_tokens: Total input tokens (including cached)
        output_tokens: Output tokens
        cached_tokens: Cached input tokens (subset of input_tokens)
        caller: Name of the calling function/module (e.g., "llm_batch", "tag_generator")
        note: Optional note (e.g., "batch 1/4, 25 items")

    Returns:
        Estimated cost in USD.
    """
    cost = estimate_cost(model, input_tokens, output_tokens, cached_tokens)
    timestamp = _get_timestamp()
    today = _get_today_str()
    log_path = _get_log_path()

    # Check if file exists and if today's section already started
    file_exists = os.path.exists(log_path)
    today_section_exists = False
    needs_new_table_header = False

    if file_exists:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        today_section_exists = f"## {today}" in content
        # If today's section exists, check if the last non-empty line is a
        # TOTAL/Subtotal row or a blank line after one — meaning a new scrape
        # batch is starting and needs its own table header.
        if today_section_exists:
            stripped_lines = [l for l in content.rstrip().splitlines() if l.strip()]
            if stripped_lines:
                last_line = stripped_lines[-1].strip()
                if "**TOTAL**" in last_line or "**Subtotal**" in last_line or "**DAILY TOTAL**" in last_line:
                    needs_new_table_header = True

    TABLE_HEADER = (
        "| Time | Model | Caller | Input | Cached | Output | Total | Cost (USD) | Note |\n"
        "|------|-------|--------|------:|-------:|-------:|------:|-----------:|------|\n"
    )

    with open(log_path, "a", encoding="utf-8") as f:
        if not file_exists:
            # Write file header
            f.write("# OpenAI API Token Usage Log\n\n")
            f.write("This file tracks all OpenAI API calls made by the Hacker News Daily pipeline.\n")
            f.write("Each entry records the model, token counts, and estimated cost.\n\n")
            f.write("**Pricing source:** [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing/)\n\n")
            f.write("---\n\n")

        if not today_section_exists:
            f.write(f"## {today}\n\n")
            f.write(TABLE_HEADER)
        elif needs_new_table_header:
            f.write(TABLE_HEADER)

        total = input_tokens + output_tokens
        time_short = datetime.now(PST).strftime("%H:%M:%S")
        note_clean = note.replace("|", "/")

        f.write(
            f"| {time_short} "
            f"| {model} "
            f"| {caller} "
            f"| {input_tokens:,} "
            f"| {cached_tokens:,} "
            f"| {output_tokens:,} "
            f"| {total:,} "
            f"| ${cost:.6f} "
            f"| {note_clean} |\n"
        )

    # Update session accumulator
    global _session_tokens, _session_cost, _session_calls
    _session_tokens += total
    _session_cost += cost
    _session_calls += 1

    # Also print to console for pipeline visibility
    print(
        f"[TOKEN] {model} | in={input_tokens:,} cached={cached_tokens:,} "
        f"out={output_tokens:,} total={input_tokens + output_tokens:,} | "
        f"cost=${cost:.6f} | {caller} {note}"
    )

    return cost


def log_daily_summary() -> None:
    """
    Append a subtotal row for the current scrape batch in today's section.
    Only counts entries after the last Subtotal/TOTAL row (i.e., the current batch).
    """
    log_path = _get_log_path()
    today = _get_today_str()

    if not os.path.exists(log_path):
        return

    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find today's section and parse only the CURRENT batch entries
    # (entries after the last **TOTAL** / **Subtotal** row)
    in_today = False
    batch_input = 0
    batch_cached = 0
    batch_output = 0
    batch_cost = 0.0
    batch_count = 0

    for line in lines:
        if line.strip() == f"## {today}":
            in_today = True
            continue
        if in_today and line.startswith("## "):
            break  # Next day's section
        if in_today and ("**TOTAL**" in line or "**Subtotal**" in line or "**DAILY TOTAL**" in line):
            # Reset counters — we only want the current batch
            batch_input = 0
            batch_cached = 0
            batch_output = 0
            batch_cost = 0.0
            batch_count = 0
            continue
        if in_today and line.startswith("| ") and not line.startswith("| Time") and not line.startswith("|---") and not line.startswith("| **"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 9:
                try:
                    batch_input += int(parts[4].replace(",", ""))
                    batch_cached += int(parts[5].replace(",", ""))
                    batch_output += int(parts[6].replace(",", ""))
                    cost_str = parts[8].replace("$", "")
                    batch_cost += float(cost_str)
                    batch_count += 1
                except (ValueError, IndexError):
                    pass

    if batch_count == 0:
        return

    batch_tokens = batch_input + batch_output

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(
            f"| **Subtotal** "
            f"| **{batch_count} calls** "
            f"| — "
            f"| **{batch_input:,}** "
            f"| **{batch_cached:,}** "
            f"| **{batch_output:,}** "
            f"| **{batch_tokens:,}** "
            f"| **${batch_cost:.6f}** "
            f"| Scrape batch |\n"
        )
        f.write(f"\n")

    print(
        f"[TOKEN] Batch subtotal: {batch_count} calls | "
        f"in={batch_input:,} out={batch_output:,} total={batch_tokens:,} | "
        f"cost=${batch_cost:.6f}"
    )


# ---------------------------------------------------------------------------
# Helper: extract usage from OpenAI response object
# ---------------------------------------------------------------------------

def extract_usage(resp) -> dict:
    """
    Extract token usage from an OpenAI Responses API response object.
    Returns a dict with keys: input_tokens, output_tokens, cached_tokens, total_tokens.
    """
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "total_tokens": 0}

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)

    # Extract cached tokens from details
    input_details = getattr(usage, "input_tokens_details", None)
    cached_tokens = 0
    if input_details:
        cached_tokens = getattr(input_details, "cached_tokens", 0) or 0

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
    }
