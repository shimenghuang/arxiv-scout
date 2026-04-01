"""
analysis.py — build the analysis prompt that Claude Code will execute, and
format the final ranked report from Claude's JSON output.

The key design principle: this module never calls an LLM itself. Instead,
`build_analysis_prompt` returns a fully-formed prompt string. The MCP tool
hands that string back to Claude Code (the caller), which then executes the
reasoning. This means zero additional API costs.
"""

import json
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
_ANALYZE_TEMPLATE_PATH = _PROMPTS_DIR / "analyze.md"


def build_analysis_prompt(profile: dict) -> str:
    """
    Assemble the analysis prompt by loading the template from prompts/analyze.md
    and substituting {user_profile}.

    Papers are already in Claude's context from fetch_papers — no need to re-embed them.
    `profile` is the dict returned by get_user_profile.

    Returns the complete prompt string ready for Claude to execute.
    """
    template = _ANALYZE_TEMPLATE_PATH.read_text(encoding="utf-8")
    profile_text = _format_profile(profile)
    return template.replace("{user_profile}", profile_text)


def _format_profile(profile: dict) -> str:
    """Convert the profile dict to a readable text block for the prompt."""
    lines = []

    research_areas = profile.get("arxiv_categories", [])
    if research_areas:
        lines.append(f"Research areas (arxiv categories): {', '.join(research_areas)}")

    keywords = [k for k in profile.get("keywords", []) if k.strip()]
    if keywords:
        lines.append(f"Keywords of interest: {', '.join(keywords)}")

    ranking_criteria = profile.get("ranking_criteria", "")
    if ranking_criteria:
        lines.append(f"Ranking criteria: {ranking_criteria}")

    past_papers = profile.get("past_papers", [])
    if past_papers:
        lines.append("\nUser's past papers (from Google Scholar):")
        for title in past_papers[:30]:  # cap at 30 to keep prompt manageable
            lines.append(f"  - {title}")
    else:
        lines.append("\nNo past papers loaded (configure scholar_url in user_profile.yaml for personalized relevance scoring).")

    scholar_fetched = profile.get("scholar_fetched", False)
    if profile.get("scholar_url") and not scholar_fetched:
        lines.append("\nNote: Google Scholar fetch failed — relevance scoring based on keywords only.")

    return "\n".join(lines)


def rank_and_display(analysis_json: str | list, top_n: int = 10) -> str:
    """
    Parse Claude's JSON output (list of paper analysis objects), sort by
    novelty_score descending, and format the top-N results as markdown.

    `analysis_json` can be a JSON string or an already-parsed list.
    Returns a markdown string suitable for display in Claude Code.
    """
    if isinstance(analysis_json, str):
        # Strip markdown code fences if Claude wrapped the JSON
        clean = analysis_json.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            # Drop first and last lines (the ``` fences)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            clean = "\n".join(inner)
        papers = json.loads(clean)
    else:
        papers = analysis_json

    if not papers:
        return "No papers were analyzed."

    # Sort by novelty_score (descending), then title alphabetically as tiebreaker
    sorted_papers = sorted(
        papers,
        key=lambda p: (-float(p.get("novelty_score", 0)), p.get("title", "")),
    )
    top = sorted_papers[:top_n]

    sections = [f"# arxiv Scout Report — Top {len(top)} Papers\n"]

    for rank, paper in enumerate(top, start=1):
        score = paper.get("novelty_score", "?")
        title = paper.get("title", "Untitled")
        paper_id = paper.get("paper_id", "")
        problem = paper.get("problem", "")
        solution = paper.get("solution", "")
        limitations = paper.get("limitations", "")
        relevance = paper.get("relevance", "")
        ideas = paper.get("paper_ideas", "")

        arxiv_url = f"https://arxiv.org/abs/{paper_id}" if paper_id else ""
        url_line = f"[{paper_id}]({arxiv_url})" if arxiv_url else paper_id

        block = [
            f"## {rank}. {title}",
            f"**Score:** {score}/10  |  **Paper:** {url_line}",
            "",
        ]

        if problem:
            block += [f"**Problem:** {problem}", ""]
        if solution:
            block += [f"**Solution:** {solution}", ""]
        if limitations:
            block += [f"**Limitations:** {limitations}", ""]
        if relevance:
            block += [f"**Relevance to your work:** {relevance}", ""]
        if ideas:
            block += [f"**Research ideas this opens up:** {ideas}", ""]

        sections.append("\n".join(block))

    return "\n---\n".join(sections)
