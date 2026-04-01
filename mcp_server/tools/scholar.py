"""
scholar.py — parse a Google Scholar profile page to extract the user's paper titles.

Google Scholar frequently blocks automated requests, so all failures are handled
gracefully: the function returns an empty list and the rest of the pipeline
continues with just the config-file keywords.
"""

import re
import urllib.request
from typing import Optional

# Scholar renders paper titles inside anchor tags with this class
_TITLE_PATTERN = re.compile(r'class="gsc_a_at"[^>]*>([^<]+)<', re.IGNORECASE)

# A realistic browser User-Agent reduces (but does not eliminate) blocking
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_scholar_titles(scholar_url: str, timeout: int = 15) -> list[str]:
    """
    Fetch the Google Scholar profile page at `scholar_url` and return a list
    of paper titles found on it.

    Returns an empty list on any error (network failure, bot detection, etc.)
    so callers can treat it as an optional enhancement.
    """
    if not scholar_url or not scholar_url.strip():
        return []

    url = scholar_url.strip()
    # Ensure we get a reasonable number of results by requesting sorted by date
    if "sortby=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sortby=pubdate&pagesize=100"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        # Network error, timeout, HTTP error, etc. — degrade gracefully
        return []

    # Check for CAPTCHA / bot-detection page
    if "unusual traffic" in html.lower() or "recaptcha" in html.lower():
        return []

    titles = _TITLE_PATTERN.findall(html)
    # Decode any HTML entities (&amp; → &, etc.) — basic set only
    cleaned = [_unescape(t.strip()) for t in titles if t.strip()]
    return cleaned


def _unescape(text: str) -> str:
    """Minimal HTML entity decoding for the characters that appear in paper titles."""
    replacements = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    return text


def build_profile_from_scholar(scholar_url: str) -> dict:
    """
    Convenience wrapper that returns a dict with a `past_papers` key containing
    the list of titles, plus a `scholar_fetched` boolean indicating success.
    """
    titles = fetch_scholar_titles(scholar_url)
    return {
        "past_papers": titles,
        "scholar_fetched": len(titles) > 0,
    }
