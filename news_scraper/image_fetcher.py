import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, Optional


MAX_HTML_BYTES = 512 * 1024

def _is_http_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https")
    except Exception:
        return False


def _extract_image_url(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    """Extract an absolute preview image URL from an already-parsed page."""
    candidates = [
        soup.find("meta", attrs={"property": "og:image"}),
        soup.find("meta", attrs={"name": "twitter:image"}),
        soup.find("img"),
    ]
    for tag in candidates:
        if not tag:
            continue
        value = tag.get("content") or tag.get("src")
        if not value:
            continue
        image_url = urljoin(page_url, value.strip())
        if _is_http_url(image_url):
            return image_url
    return None


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _extract_article_text(soup: BeautifulSoup, max_chars: int) -> str:
    """Return a bounded, best-effort article excerpt for LLM summarization."""
    if max_chars <= 0:
        return ""

    parts = []
    seen = set()

    for attrs in (
        {"property": "og:description"},
        {"name": "description"},
        {"name": "twitter:description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        text = _clean_text(tag.get("content", "") if tag else "")
        if text and text not in seen:
            parts.append(text)
            seen.add(text)

    noise_selectors = (
        "script, style, noscript, nav, footer, header, aside, form, "
        "[class*='advert'], [class*='cookie'], [class*='consent'], "
        "[class*='newsletter'], [class*='related'], [class*='recommend'], "
        "[class*='social'], [class*='share'], [id*='advert'], [id*='cookie']"
    )
    for unwanted in soup.select(noise_selectors):
        unwanted.decompose()

    root = soup.find("article") or soup.find("main") or soup.body or soup
    # Paragraphs are much less likely than list items to contain menus, ads,
    # related links, or other page chrome. News pages normally put the essential
    # lead at the start, so two substantial paragraphs are enough context for a
    # short digest and avoid sending most of the article to the model.
    paragraph_count = 0
    for tag in root.find_all("p"):
        text = _clean_text(tag.get_text(" ", strip=True))
        if len(text) < 40 or text in seen:
            continue
        parts.append(text)
        seen.add(text)
        paragraph_count += 1
        if paragraph_count >= 2 or sum(len(part) + 1 for part in parts) >= max_chars:
            break

    return "\n".join(parts)[:max_chars].strip()


def fetch_page_context(
    page_url: str,
    timeout_seconds: int = 15,
    user_agent: str = "Mozilla/5.0",
    max_article_chars: int = 4000,
) -> Dict[str, Optional[str]]:
    """
    Fetch a page once and return both its preview image and a bounded article
    excerpt. The excerpt is transient input for the LLM and is not persisted.
    """
    result: Dict[str, Optional[str]] = {"image_url": None, "article_context": ""}
    if not _is_http_url(page_url):
        return result

    try:
        response = requests.get(
            page_url,
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if content_type and "html" not in content_type and "xml" not in content_type:
            return result
        chunks = []
        downloaded = 0
        for chunk in response.iter_content(chunk_size=16384):
            if not chunk:
                continue
            remaining = MAX_HTML_BYTES - downloaded
            if remaining <= 0:
                break
            chunks.append(chunk[:remaining])
            downloaded += min(len(chunk), remaining)
            if downloaded >= MAX_HTML_BYTES:
                break
        raw_html = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        page_text = raw_html.decode(encoding, errors="replace")
        if not page_text.lstrip().startswith("<"):
            return result
        soup = BeautifulSoup(page_text, "html.parser")
    except Exception:
        return result

    result["image_url"] = _extract_image_url(soup, response.url or page_url)
    result["article_context"] = _extract_article_text(soup, max_article_chars)
    return result

def extract_preview_image_url(
    page_url: str,
    timeout_seconds: int = 15,
    user_agent: str = "Mozilla/5.0",
) -> Optional[str]:
    """
    Extract preview image URL from:
      - <meta property="og:image" ...>
      - <meta name="twitter:image" ...>
      - fallback: first <img> tag

    Return absolute URL or None.
    """
    return fetch_page_context(
        page_url,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
        max_article_chars=0,
    )["image_url"]
