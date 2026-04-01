# arxiv-scout

A Claude Code MCP server that fetches, analyzes, and ranks daily arxiv preprints by research opportunity — personalized to your work.

## How it works

1. **Fetch** — hits the arxiv API for today's papers in your configured categories, keyword-filters them, and caches results in SQLite (re-running the same day is instant).
2. **Profile** — reads your `config/user_profile.yaml` and optionally scrapes your Google Scholar page for past paper titles.
3. **Analyze** — prepares a structured prompt and hands it to Claude Code (which you already have open), so no separate LLM API calls are needed.
4. **Rank** — sorts Claude's analysis by novelty score and renders a clean markdown report.

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/arxiv-scout
cd arxiv-scout
uv sync
```

Or with pip:

```bash
pip install mcp httpx pyyaml
```

### 2. Edit your profile

Open `config/user_profile.yaml` and fill in:

- **`scholar_url`** — your Google Scholar profile URL (optional but gives much better relevance scoring)
- **`arxiv_categories`** — which arxiv categories to monitor (default: cs.LG, cs.CL, cs.AI)
- **`keywords`** — words/phrases to pre-filter papers by (leave empty to analyze all)
- **`ranking_criteria`** — plain-language description of what makes a paper exciting to you

### 3. Open the project in Claude Code

The project includes a `.mcp.json` that registers the arxiv-scout MCP server automatically. When you open the project directory in Claude Code, it will prompt you to trust the server — approve it, and you're done.

No manual `claude mcp add` needed.

### 4. Run

In Claude Code, type:

```
/scout
```

Claude will fetch today's papers, analyze them against your profile, and display a ranked report.

Optionally pass a date to scout a specific day:

```
/scout 2026-03-31
```

## Project structure

```
arxiv-scout/
├── .mcp.json                   ← auto-registers the MCP server with Claude Code
├── .claude/
│   ├── settings.json           ← pre-approves MCP tool calls (no per-step prompts)
│   └── skills/scout/
│       └── SKILL.md            ← /scout skill definition
├── mcp_server/
│   ├── server.py               ← MCP server (stdio transport)
│   └── tools/
│       ├── arxiv.py            ← arxiv API fetch + SQLite cache
│       ├── scholar.py          ← Google Scholar profile parser
│       └── analysis.py         ← prompt builder + report formatter
├── prompts/
│   └── analyze.md              ← analysis prompt template
├── config/
│   ├── user_profile.yaml       ← your personalization config
│   └── settings.yaml           ← display and output preferences
└── data/                       ← created at runtime (gitignored)
    ├── cache.db                ← arxiv SQLite cache
    └── reports/                ← saved markdown reports
```

## Notes

- **Google Scholar scraping** sometimes fails due to bot detection — this is expected. The tool falls back gracefully to keyword-only relevance scoring. Scholar data is cached for 30 days (configurable in `settings.yaml`).
- **arxiv cache** is per-date, so running `/scout` multiple times on the same day won't re-hit the arxiv API.
- **Token usage** — analysis is done by the Claude Code model you already have open. No additional API billing beyond your normal Claude Code usage.
