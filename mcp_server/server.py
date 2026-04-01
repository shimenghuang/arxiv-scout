"""
server.py — MCP server entry point for arxiv-scout.

Exposes four tools to Claude Code:
  - fetch_papers
  - get_user_profile
  - analyze_papers
  - rank_and_display

Run directly as a script: python mcp_server/server.py
Uses stdio transport (the standard for Claude Code MCP integrations).
"""

import datetime
import json
import sys
from pathlib import Path

import yaml

# Ensure the project root is on sys.path so sibling imports work when the
# server is launched directly (not as a module).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from mcp_server.tools.arxiv import fetch_papers as _fetch_papers, rank_papers as _rank_papers
from mcp_server.tools.scholar import build_profile_from_scholar
from mcp_server.tools.analysis import build_analysis_prompt, rank_and_display as _rank_and_display

_PROFILE_PATH = _PROJECT_ROOT / "config" / "user_profile.yaml"
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"

app = Server("arxiv-scout")


def _load_profile() -> dict:
    """Load user_profile.yaml, returning defaults if the file is missing or malformed."""
    defaults = {
        "scholar_url": "",
        "arxiv_categories": ["cs.LG", "cs.CL", "cs.AI"],
        "keywords": [],
        "ranking_criteria": "prioritize novel research directions with clear empirical methodology",
    }
    if not _PROFILE_PATH.exists():
        return defaults
    try:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {**defaults, **{k: v for k, v in data.items() if v is not None}}
    except Exception:
        return defaults


def _load_settings() -> dict:
    """Load settings.yaml, returning defaults if the file is missing or malformed."""
    defaults = {
        "top_n": 10,
        "max_papers_to_fetch": 200,
        "max_papers_to_analyze": 50,
        "save_output": True,
        "output_dir": "data/reports",
        "scholar_cache_ttl_days": 30,
    }
    if not _SETTINGS_PATH.exists():
        return defaults
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {**defaults, **{k: v for k, v in data.items() if v is not None}}
    except Exception:
        return defaults


_SCHOLAR_CACHE_PATH = _PROJECT_ROOT / "data" / ".scholar_cache.json"
_ANALYSIS_CACHE_PATH = _PROJECT_ROOT / "data" / ".analysis_cache.json"


def _load_scholar_cache(scholar_url: str) -> dict:
    """Return cached Scholar data if fresh, otherwise re-fetch and cache.
    TTL is read from settings.yaml (scholar_cache_ttl_days)."""
    ttl_days = _load_settings().get("scholar_cache_ttl_days", 30)
    if _SCHOLAR_CACHE_PATH.exists():
        try:
            cached = json.loads(_SCHOLAR_CACHE_PATH.read_text(encoding="utf-8"))
            fetched_on = datetime.date.fromisoformat(cached.get("fetched_on", "2000-01-01"))
            if (datetime.date.today() - fetched_on).days < ttl_days:
                return {"past_papers": cached["past_papers"], "scholar_fetched": True}
        except Exception:
            pass
    data = build_profile_from_scholar(scholar_url)
    if data["scholar_fetched"]:
        _SCHOLAR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SCHOLAR_CACHE_PATH.write_text(
            json.dumps({"fetched_on": datetime.date.today().isoformat(), "past_papers": data["past_papers"]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return data


def _save_report(report: str, output_dir: str, date_str: str | None = None) -> Path:
    """Save report to a dated markdown file, avoiding overwrites. Returns the path written."""
    out_dir = _PROJECT_ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if not date_str:
        date_str = datetime.date.today().isoformat()
    path = out_dir / f"{date_str}.md"
    suffix = 2
    while path.exists():
        path = out_dir / f"{date_str}_{suffix}.md"
        suffix += 1
    path.write_text(report, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_papers",
            description=(
                "Fetch today's arxiv preprints in the user's configured categories. "
                "Results are keyword-filtered and cached in SQLite so repeat calls "
                "within the same day are instant. "
                "Returns a JSON list of papers: {paper_id, title, authors, abstract, url, submitted}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD) to fetch papers for. Defaults to today.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_user_profile",
            description=(
                "Read the user's research profile from config/user_profile.yaml "
                "and optionally fetch their Google Scholar page to extract past paper titles. "
                "Returns a JSON object with: categories, keywords, ranking_criteria, "
                "past_papers (list of titles), scholar_fetched (bool), top_n, max_papers_to_analyze."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="analyze_papers",
            description=(
                "Prepare the analysis prompt. "
                "This tool does NOT call an LLM — it returns a structured prompt "
                "that YOU (Claude) should then execute to produce the analysis JSON. "
                "Takes no arguments; reads the profile internally."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="rank_and_display",
            description=(
                "Sort Claude's analysis by novelty score and render the top-N papers "
                "as a readable markdown report."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_json": {
                        "description": "The structured analysis array produced by Claude.",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top papers to include. Defaults to the value in user_profile.yaml.",
                    },
                    "scout_date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD) of the papers being scouted. Used for the report filename. Defaults to today.",
                    },
                },
                "required": ["analysis_json"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "fetch_papers":
        profile = _load_profile()
        settings = _load_settings()
        target_date = arguments.get("target_date")

        papers = _fetch_papers(
            categories=profile["arxiv_categories"],
            keywords=profile["keywords"],
            max_results=settings["max_papers_to_fetch"],
            target_date=target_date,
        )

        # Load past papers for relevance scoring (uses cache, no network call if fresh)
        past_papers: list[str] = []
        if profile.get("scholar_url"):
            scholar_data = _load_scholar_cache(profile["scholar_url"])
            past_papers = scholar_data.get("past_papers", [])

        # Rank by relevance, then cap to max_papers_to_analyze
        papers = _rank_papers(papers, profile["keywords"], past_papers)
        cap = settings["max_papers_to_analyze"]
        if len(papers) > cap:
            papers = papers[:cap]

        result = {
            "count": len(papers),
            "papers": papers,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_user_profile":
        profile_cfg = _load_profile()
        settings = _load_settings()

        scholar_data = {"past_papers": [], "scholar_fetched": False}
        if profile_cfg.get("scholar_url"):
            scholar_data = _load_scholar_cache(profile_cfg["scholar_url"])

        profile = {
            "arxiv_categories": profile_cfg["arxiv_categories"],
            "keywords": profile_cfg["keywords"],
            "ranking_criteria": profile_cfg["ranking_criteria"],
            "top_n": settings["top_n"],
            "max_papers_to_analyze": settings["max_papers_to_analyze"],
            "scholar_url": profile_cfg.get("scholar_url", ""),
            "past_papers": scholar_data["past_papers"],
            "scholar_fetched": scholar_data["scholar_fetched"],
        }
        return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]

    elif name == "analyze_papers":
        profile_cfg = _load_profile()
        settings = _load_settings()
        profile = {
            "arxiv_categories": profile_cfg["arxiv_categories"],
            "keywords": profile_cfg["keywords"],
            "ranking_criteria": profile_cfg["ranking_criteria"],
            "top_n": settings["top_n"],
            "max_papers_to_analyze": settings["max_papers_to_analyze"],
        }
        prompt = build_analysis_prompt(profile)
        return [TextContent(type="text", text=prompt)]

    elif name == "rank_and_display":
        analysis_json = arguments.get("analysis_json")
        if not analysis_json:
            return [TextContent(type="text", text="No analysis_json provided.")]
        if not isinstance(analysis_json, str):
            import json as _json
            analysis_json = _json.dumps(analysis_json)
        settings = _load_settings()
        top_n = arguments.get("top_n", settings["top_n"])

        report = _rank_and_display(analysis_json, top_n=top_n)

        if settings.get("save_output"):
            scout_date = arguments.get("scout_date")
            saved_path = _save_report(report, settings["output_dir"], date_str=scout_date)
            report += f"\n\n---\n*Report saved to `{saved_path.relative_to(_PROJECT_ROOT)}`*"

        return [TextContent(type="text", text=report)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
