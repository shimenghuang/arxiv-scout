"""
arxiv.py — fetch today's papers from the arxiv API and cache them in SQLite.

Uses only stdlib urllib to hit the Atom API endpoint. Papers are pre-filtered
by keyword match against title+abstract before being returned, so the caller
only sees papers relevant to the user's configured interests.
"""

import sqlite3
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# SQLite DB lives in data/ relative to the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "cache.db"

_ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


def _ensure_db() -> sqlite3.Connection:
    """Open (or create) the cache database and return a connection."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            date        TEXT NOT NULL,
            category    TEXT NOT NULL,
            paper_id    TEXT NOT NULL,
            title       TEXT NOT NULL,
            authors     TEXT NOT NULL,
            abstract    TEXT NOT NULL,
            url         TEXT NOT NULL,
            submitted   TEXT NOT NULL,
            PRIMARY KEY (date, paper_id)
        )
    """)
    conn.commit()
    return conn


def _fetch_from_arxiv(categories: list[str], max_results: int) -> list[dict[str, Any]]:
    """Hit the arxiv Atom API and return parsed paper dicts."""
    # Build the search query: cat:cs.LG OR cat:cs.CL OR ...
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    params = urllib.parse.urlencode({
        "search_query": cat_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{_ARXIV_API}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-scout/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_bytes = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(5 * 2 ** attempt)  # 5s, 10s, 20s
            else:
                raise
    else:
        raise RuntimeError("arxiv API returned 429 after retries")

    root = ET.fromstring(xml_bytes)
    papers = []

    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        # Skip the first <entry> if it's the feed summary (no arxiv id tag)
        id_el = entry.find(f"{{{_ATOM_NS}}}id")
        if id_el is None or "abs" not in (id_el.text or ""):
            continue

        raw_id = id_el.text.strip()
        # Extract the short id like "2401.12345v1"
        paper_id = raw_id.split("/abs/")[-1]

        title_el = entry.find(f"{{{_ATOM_NS}}}title")
        title = " ".join((title_el.text or "").split())  # collapse whitespace

        abstract_el = entry.find(f"{{{_ATOM_NS}}}summary")
        abstract = " ".join((abstract_el.text or "").split())

        authors = [
            author.find(f"{{{_ATOM_NS}}}name").text.strip()
            for author in entry.findall(f"{{{_ATOM_NS}}}author")
            if author.find(f"{{{_ATOM_NS}}}name") is not None
        ]

        published_el = entry.find(f"{{{_ATOM_NS}}}published")
        submitted = (published_el.text or "").strip()

        papers.append({
            "paper_id": paper_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": raw_id.replace("/abs/", "/pdf/"),  # direct PDF link
            "submitted": submitted,
        })

    return papers


def _cache_papers(conn: sqlite3.Connection, cache_date: str, categories: list[str], papers: list[dict]) -> None:
    """Insert papers into the cache. Ignores duplicates (same date+paper_id)."""
    category_str = ",".join(sorted(categories))
    rows = [
        (
            cache_date,
            category_str,
            p["paper_id"],
            p["title"],
            "|".join(p["authors"]),
            p["abstract"],
            p["url"],
            p["submitted"],
        )
        for p in papers
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO papers (date, category, paper_id, title, authors, abstract, url, submitted) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def _load_from_cache(conn: sqlite3.Connection, cache_date: str) -> list[dict]:
    """Return all papers cached for the given date."""
    rows = conn.execute(
        "SELECT paper_id, title, authors, abstract, url, submitted FROM papers WHERE date = ?",
        (cache_date,),
    ).fetchall()
    return [
        {
            "paper_id": row[0],
            "title": row[1],
            "authors": row[2].split("|"),
            "abstract": row[3],
            "url": row[4],
            "submitted": row[5],
        }
        for row in rows
    ]


def _filter_by_target_date(papers: list[dict], target_date: str) -> list[dict]:
    """Return papers submitted on the most recent business day before target_date.
    Looks back up to 4 days to handle weekends and holidays."""
    target = date.fromisoformat(target_date)
    for days_back in range(1, 5):
        submission_date = target - timedelta(days=days_back)
        matching = []
        for paper in papers:
            try:
                submitted = datetime.fromisoformat(
                    paper["submitted"].replace("Z", "+00:00")
                ).date()
                if submitted == submission_date:
                    matching.append(paper)
            except Exception:
                pass
        if matching:
            return matching
    return []


def _keyword_filter(papers: list[dict], keywords: list[str]) -> list[dict]:
    """Keep only papers whose title or abstract contains at least one keyword (case-insensitive).
    If no keywords are configured, all papers pass through."""
    if not keywords or all(k.strip() == "" for k in keywords):
        return papers

    lower_keywords = [k.lower() for k in keywords if k.strip()]
    filtered = []
    for paper in papers:
        haystack = (paper["title"] + " " + paper["abstract"]).lower()
        if any(kw in haystack for kw in lower_keywords):
            filtered.append(paper)
    return filtered


_STOP_WORDS = {
    "a", "an", "the", "of", "in", "for", "on", "with", "to", "and", "or",
    "is", "are", "via", "from", "by", "as", "at", "its", "we", "our",
}


def rank_papers(
    papers: list[dict],
    keywords: list[str],
    past_papers: list[str],
) -> list[dict]:
    """Score and sort papers by relevance to the user profile.

    Scoring components:
    - Keyword density: occurrences in title (3×) + abstract (1×)
    - Past-paper word overlap: meaningful title-word matches with user's own papers (2× each)

    Papers are returned sorted by score descending. Papers with equal scores
    preserve their original order (stable sort).
    """
    if not keywords and not past_papers:
        return papers

    lower_keywords = [k.lower() for k in keywords if k.strip()]

    past_words: set[str] = set()
    for title in past_papers:
        for word in title.lower().split():
            word = word.strip(".,;:()")
            if word not in _STOP_WORDS and len(word) > 2:
                past_words.add(word)

    def _score(paper: dict) -> float:
        title_lower = paper["title"].lower()
        abstract_lower = paper["abstract"].lower()
        score = 0.0

        for kw in lower_keywords:
            score += title_lower.count(kw) * 3
            score += abstract_lower.count(kw)

        if past_words:
            title_words = {w.strip(".,;:()") for w in title_lower.split()}
            score += len(title_words & past_words) * 2

        return score

    return sorted(papers, key=_score, reverse=True)


def fetch_papers(
    categories: list[str],
    keywords: list[str],
    max_results: int = 200,
    target_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Main entry point called by the MCP tool.

    Without target_date: fetches the latest papers (no date filter), cached under today.
    With target_date: fetches and filters to papers submitted on the most recent
    business day before target_date, cached under target_date.

    Returns list of dicts: {paper_id, title, authors, abstract, url, submitted}
    """
    explicit_date = target_date is not None
    cache_key = target_date if explicit_date else date.today().isoformat()

    conn = _ensure_db()
    cached = _load_from_cache(conn, cache_key)

    if cached:
        papers = cached
    else:
        papers = _fetch_from_arxiv(categories, max_results)
        if explicit_date:
            papers = _filter_by_target_date(papers, target_date)
        if papers:
            _cache_papers(conn, cache_key, categories, papers)

    conn.close()
    return _keyword_filter(papers, keywords)
