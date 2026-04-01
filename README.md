# arxiv-scout

An MCP server for Claude Code that fetches, analyzes, and ranks daily arxiv preprints by research opportunity — personalized to your work.

## How it works

1. **Fetch** — hits the arxiv API for today's papers in your configured categories, keyword-filters them, and caches results in SQLite (so re-running the same day is instant).
2. **Profile** — reads your `config/user_profile.yaml` and optionally scrapes your Google Scholar page for past paper titles.
3. **Analyze** — prepares a structured prompt and hands it to Claude Code (which you already have open), so no separate LLM API calls are needed.
4. **Rank** — sorts Claude's analysis by novelty score and renders a clean markdown report.

## Setup

### 1. Install dependencies

```bash
pip install mcp httpx pyyaml
```

(`httpx` is available as a fallback for Scholar fetching; `mcp` is the MCP Python SDK; `pyyaml` reads your config.)

### 2. Edit your profile

Open `config/user_profile.yaml` and fill in:

- **`scholar_url`** — your Google Scholar profile URL (optional but gives much better relevance scoring)
- **`arxiv_categories`** — which arxiv categories to monitor (default: cs.LG, cs.CL, cs.AI)
- **`keywords`** — words/phrases to pre-filter papers by (leave empty to analyze all)
- **`ranking_criteria`** — plain-language description of what makes a paper exciting to you
- **`top_n`** — how many papers to show in the final report

### 3. Register with Claude Code

Add this to your Claude Code MCP configuration (usually `~/.claude/mcp_config.json` or via `claude mcp add`):

```json
{
  "arxiv-scout": {
    "command": "python",
    "args": ["/home/shuang/Documents/projects/arxiv-scout/mcp_server/server.py"]
  }
}
```

Or use the CLI:

```bash
claude mcp add arxiv-scout python /home/shuang/Documents/projects/arxiv-scout/mcp_server/server.py
```

### 4. Install the skill

Copy (or symlink) `claude/skill.md` into your Claude Code skills directory:

```bash
mkdir -p ~/.claude/skills
cp /home/shuang/Documents/projects/arxiv-scout/claude/skill.md ~/.claude/skills/scout.md
```

### 5. Run

In Claude Code, type:

```
/scout
```

Claude will fetch today's papers, analyze them against your profile, and display a ranked report.

## Project structure

```
arxiv-scout/
├── mcp_server/
│   ├── server.py           ← MCP server (stdio transport)
│   └── tools/
│       ├── arxiv.py        ← arxiv API fetch + SQLite cache
│       ├── scholar.py      ← Google Scholar profile parser
│       └── analysis.py     ← prompt builder + report formatter
├── prompts/
│   └── analyze.md          ← analysis prompt template
├── data/
│   └── cache.db            ← created at runtime
├── config/
│   └── user_profile.yaml   ← your personalization config
└── claude/
    └── skill.md            ← /scout skill definition
```

## Notes

- **Google Scholar scraping** sometimes fails due to bot detection — this is expected. The tool falls back gracefully to keyword-only relevance scoring.
- **Cache** is per-date, so running `/scout` multiple times on the same day won't re-hit the arxiv API.
- **Token usage** — analysis is done by the Claude Code model you already have open. No additional API billing.
- The `data/cache.db` file is created automatically on first run.
