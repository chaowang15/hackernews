"""
LLM batch enrichment: translate titles and generate bilingual summaries
for a batch of Hacker News story items.

Features:
- Robust JSON parsing (handles markdown fences, extra data, concatenated output)
- Content cleaning (strips control chars, normalizes whitespace, removes meta-commentary)
- Comprehensive logging for debugging in GitHub Actions
- Retry logic with configurable max_retries
"""

import json
import re
import time
import traceback
from typing import Any, Dict, List

from openai import OpenAI

from token_logger import log_token_usage, extract_usage


# ---------------------------------------------------------------------------
# Robust JSON parser
# ---------------------------------------------------------------------------

def _safe_json_loads(text: str) -> Any:
    """Parse JSON from LLM output, handling common issues like
    markdown fences, extra trailing data, and concatenated objects."""
    s = text.strip()

    # Strip markdown code fences if present
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        s = "\n".join(lines).strip()

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Locate the first JSON token
    idxs = [i for i in [s.find("["), s.find("{")] if i != -1]
    if not idxs:
        raise RuntimeError(f"LLM output is not JSON: {s[:300]}")
    s2 = s[min(idxs):]

    # Use JSONDecoder to parse only the first valid JSON value
    # This handles "Extra data" errors from concatenated output
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(s2)
        return obj
    except json.JSONDecodeError:
        pass

    return json.loads(s2)


# ---------------------------------------------------------------------------
# Content cleaning utilities
# ---------------------------------------------------------------------------

# Patterns for meta-commentary that should be removed from summaries
_META_PATTERNS = [
    re.compile(r"^(The\s+)?(linked\s+)?(article|post|page|piece|blog\s+post|URL)\s+(discusses|explores|highlights|describes|examines|covers|points\s+to|links\s+to)\b", re.IGNORECASE),
    re.compile(r"\b(this|the)\s+summary\s+(is\s+based|uses|relies)\s+on\b", re.IGNORECASE),
    re.compile(r"\bthe\s+URL\s+points?\s+to\b", re.IGNORECASE),
    re.compile(r"\bbased\s+(solely\s+)?on\s+the\s+(title|URL)\s+(and\s+(URL|title)\s+)?context\b", re.IGNORECASE),
    re.compile(r"\bno\s+additional\s+(claims|information|details)\b", re.IGNORECASE),
    re.compile(r"\bthe\s+snippet\s+relies\s+on\b", re.IGNORECASE),
]


def _clean_text(text: str) -> str:
    """Clean a single text field: strip control chars, normalize whitespace."""
    if not text:
        return ""
    # Remove control characters (except newline/tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_summary(summary: str) -> str:
    """Clean a summary: remove meta-commentary sentences, normalize whitespace."""
    summary = _clean_text(summary)
    if not summary:
        return ""

    # Split into sentences and filter out meta-commentary
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    cleaned = []
    for sent in sentences:
        is_meta = any(pat.search(sent) for pat in _META_PATTERNS)
        if not is_meta:
            cleaned.append(sent)

    result = " ".join(cleaned).strip()
    # If everything was filtered out, keep the original (better than empty)
    return result if result else summary


def _clean_enrichment(obj: Dict[str, str]) -> Dict[str, str]:
    """Clean all fields of an enrichment result."""
    return {
        "title_zh": _clean_text(obj.get("title_zh", "")),
        "summary_en": _clean_summary(obj.get("summary_en", "")),
        "summary_zh": _clean_summary(obj.get("summary_zh", "")),
    }


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

def llm_enrich_batch(
    items: List[Dict[str, str]],
    model: str = "gpt-5-nano",
    max_retries: int = 2,
) -> Dict[int, Dict[str, str]]:
    """
    Enrich a batch of HN story items with Chinese titles and bilingual summaries.

    items: [{"id": int, "title_en": str, "url": str}]
    return: id -> {"title_zh", "summary_en", "summary_zh"}
    """
    client = OpenAI()

    input_payload = [
        {
            "id": int(it["id"]),
            "title_en": it["title_en"],
            "url": it["url"],
            "article_context": it.get("article_context", ""),
            "context_mode": "source_excerpt" if it.get("article_context") else "title_only",
        }
        for it in items
    ]

    prompt = f"""You are a tech news editor writing brief, insightful summaries for a Hacker News daily digest.

For each item below, produce:
- title_zh: Natural, concise Chinese translation of title_en.
- summary_en: When context_mode is source_excerpt, write a factual 3-4 sentence
  English summary grounded in article_context.
  The first 2-3 sentences must summarize what the source reports: what happened,
  who/what is involved, and the important concrete details or outcome. The final
  sentence may explain significance or likely impact, but only when supported by
  the supplied context. It must not be a personal opinion.
- summary_zh: A natural Chinese rendering of the same facts and structure as
  summary_en. Keep the factual sentences factual; include at most the same one
  final significance sentence. Do not add claims absent from summary_en.

STRICT RULES:
- When context_mode is title_only because source fetching failed or yielded no
  reliable text, fall back safely to the earlier title-based behavior. Write a
  concise 1-2 sentence description using only facts directly established by
  title_en. State the subject directly and naturally. Never say "the title",
  "the supplied context", "the provided information", or similar phrases.
  Do not infer missing people, causes, outcomes, numbers, or details.
- A title_only item is an expected per-item fallback and must still be returned
  in the JSON array; never fail the batch merely because its context is empty.
- Do NOT include meta-commentary like "this summary is based on..." or "the linked article discusses...".
- Never refer to the input itself with phrases such as "the title reports",
  "the title identifies", "the context says", or "the supplied information".
- Treat article_context as the source of truth. Never invent facts, motives,
  outcomes, quotes, or background that are not supported by it.
- If article_context is empty or too sparse, summarize only what can safely be
  established from the title/context and use fewer sentences rather than guess.
- Do NOT restate the title as the summary. Add concrete source details when available.
- Do NOT mention the URL, the source website name, or where the link points to.
- Do NOT use filler phrases like "the article explores", "the post highlights", "the piece discusses".
- Do NOT use meta-analysis such as "this highlights how..." unless it is the
  single final significance sentence and is directly supported by the source.
- Start directly with the substance. Be concise, neutral, and informative.

Return STRICT JSON as an array. Each element must be:
{{
  "id": <same id>,
  "title_zh": "...",
  "summary_en": "...",
  "summary_zh": "..."
}}

Input items JSON:
{json.dumps(input_payload, ensure_ascii=False)}
"""

    print(f"[LLM] Enriching {len(items)} items with model={model} ...")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            resp = client.responses.create(
                model=model,
                input=prompt,
            )
            elapsed = time.time() - t0

            if resp.output is None:
                raise RuntimeError(
                    f"LLM returned None output. Status: {getattr(resp, 'status', 'unknown')}"
                )

            raw_text = resp.output_text.strip()
            print(f"[LLM] Response received in {elapsed:.1f}s, output length={len(raw_text)} chars")

            # Log token usage
            usage = extract_usage(resp)
            log_token_usage(
                model=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cached_tokens=usage["cached_tokens"],
                caller="llm_batch",
                note=f"enrich {len(items)} items, attempt {attempt}",
            )

            data = _safe_json_loads(raw_text)

            if not isinstance(data, list):
                raise RuntimeError(f"Expected JSON array, got: {type(data)}")

            out: Dict[int, Dict[str, str]] = {}
            for obj in data:
                if not isinstance(obj, dict) or "id" not in obj:
                    continue
                _id = int(obj["id"])
                for k in ["title_zh", "summary_en", "summary_zh"]:
                    if k not in obj or not isinstance(obj[k], str):
                        raise RuntimeError(f"Missing/invalid key {k} for id={_id}")
                out[_id] = _clean_enrichment(obj)

            missing = [int(it["id"]) for it in items if int(it["id"]) not in out]
            if missing:
                raise RuntimeError(
                    f"LLM batch missing ids: {missing[:10]} (total {len(missing)})"
                )

            print(f"[LLM] Successfully enriched {len(out)} items (attempt {attempt})")
            return out

        except Exception as e:
            last_error = e
            print(f"[LLM][WARN] Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"[LLM] Retrying in {wait}s ...")
                time.sleep(wait)

    raise RuntimeError(
        f"LLM enrichment failed after {max_retries} attempts. Last error: {last_error}"
    )
