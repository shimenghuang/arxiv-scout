# arxiv-scout

A Claude Code MCP server that fetches, analyzes, and ranks daily arxiv preprints by research opportunity — personalized to your work.

## How it works

1. **Fetch** — hits the arxiv API for today's papers in your configured categories, keyword-filters them, and caches results in SQLite (re-running the same day is instant).
2. **Profile** — reads your configuration and optionally scrapes your Google Scholar page for past paper titles to improve relevance ranking.
3. **Analyze** — prepares a structured prompt and hands it to Claude Code (which you already have open), so no separate LLM API calls are needed.
4. **Rank** — sorts Claude's analysis by novelty score and renders a clean markdown report.

## Setup

### 1. Clone and install

**With uv** (recommended — handles dependencies and MCP registration automatically):

```bash
git clone https://github.com/shimenghuang/arxiv-scout
cd arxiv-scout
uv sync
```

Install uv: [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)

**With pip** (requires manual MCP registration — see step 2b):

```bash
git clone https://github.com/shimenghuang/arxiv-scout
cd arxiv-scout
pip install mcp pyyaml
```

### 2a. Open the project in Claude Code (uv users)

```bash
claude
```

The project includes a `.mcp.json` that registers the arxiv-scout MCP server automatically. Claude Code will prompt you to trust the server on first open — approve it.

### 2b. Register the MCP server manually (pip users)

```bash
claude mcp add arxiv-scout python /path/to/arxiv-scout/mcp_server/server.py
```

Then open the project directory in Claude Code.

### 3. Configure your profile

Run the setup skill to personalize arxiv-scout to your research interests:

```
/scout-setup
```

This walks you through setting your Scholar URL, arxiv categories, keywords, and ranking preferences. Run it once — settings are saved to `~/.claude-plugin-config/arxiv-scout/` and persist across updates.

### 4. Run

```
/scout
```

Claude will fetch today's papers, analyze them against your profile, and display a ranked report. Optionally pass a date to scout a specific day:

```
/scout 2026-03-31
```

---

> **Claude Code marketplace** — arxiv-scout can also be installed via the Claude Code plugin marketplace. This has not been fully tested and may require manual MCP server registration. Feedback welcome.
>
> ```bash
> claude plugin marketplace add https://github.com/shimenghuang/arxiv-scout
> claude plugin install arxiv-scout@shimenghuang-arxiv-scout
> ```

## Project structure

```
arxiv-scout/
├── .mcp.json                       ← auto-registers the MCP server with Claude Code
├── .claude/
│   ├── settings.json               ← pre-approves MCP tool calls (no per-step prompts)
│   └── skills/
│       ├── scout/SKILL.md          ← /scout skill definition
│       └── scout-setup/SKILL.md   ← /scout-setup skill definition
├── mcp_server/
│   ├── server.py                   ← MCP server (stdio transport)
│   └── tools/
│       ├── arxiv.py                ← arxiv API fetch + SQLite cache
│       ├── scholar.py              ← Google Scholar profile parser
│       └── analysis.py            ← prompt builder + report formatter
├── prompts/
│   └── analyze.md                  ← analysis prompt template
├── config/                         ← fallback config (overridden by ~/.claude-plugin-config/arxiv-scout/)
│   ├── user_profile.yaml
│   └── settings.yaml
└── data/                           ← created at runtime (gitignored)
    ├── cache.db                    ← arxiv SQLite cache
    └── reports/                    ← saved markdown reports
```

## Notes

- **Google Scholar scraping** sometimes fails due to bot detection — this is expected. The tool falls back gracefully to keyword-only relevance scoring. Scholar data is cached for 30 days (configurable in `settings.yaml`).
- **arxiv cache** is per-date, so running `/scout` multiple times on the same day won't re-hit the arxiv API.
- **Token usage** — analysis is done by the Claude Code model you already have open. No additional API billing beyond your normal Claude Code usage.
