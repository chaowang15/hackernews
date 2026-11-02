import time
import logging
import requests
from typing import Any, Dict, List, Optional

HN_BASE = "https://hacker-news.firebaseio.com/v0"
logger = logging.getLogger(__name__)

def _get_json(url: str, timeout: int = 20, max_retries: int = 3) -> Any:
    """Fetch JSON from URL with retry and exponential backoff."""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if attempt == max_retries:
                logger.error("Failed after %d attempts for %s: %s", max_retries, url, e)
                raise
            wait = 2 ** attempt  # 2s, 4s, 8s
            logger.warning("Attempt %d/%d failed for %s (%s). Retrying in %ds...",
                           attempt, max_retries, url, type(e).__name__, wait)
            time.sleep(wait)

def get_story_ids(kind: str) -> List[int]:
    """
    kind: 'best' | 'new' | 'top'
    """
    mapping = {
        "best": f"{HN_BASE}/beststories.json",
        "new":  f"{HN_BASE}/newstories.json",
        "top":  f"{HN_BASE}/topstories.json",
    }
    if kind not in mapping:
        raise ValueError(f"Unknown kind={kind}, must be one of {list(mapping.keys())}")
    return _get_json(mapping[kind])

def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    url = f"{HN_BASE}/item/{item_id}.json"
    return _get_json(url)

def get_item_url(item: Dict[str, Any]) -> str:
    # Ask HN / Show HN 可能没有 url
    if item.get("url"):
        return item["url"]
    return f"https://news.ycombinator.com/item?id={item.get('id')}"
