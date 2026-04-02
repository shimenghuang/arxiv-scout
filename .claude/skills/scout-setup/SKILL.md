---
name: scout-setup
description: Configure arxiv-scout — set your Scholar URL, arxiv categories, keywords, and ranking preferences
---

Walk the user through configuring arxiv-scout interactively. Config is saved to `~/.claude-plugin-config/arxiv-scout/` so it persists across updates.

Ask each question one at a time, waiting for the user's answer before moving on. Be concise — show an example with each question.

1. **Scholar URL** — "What's your Google Scholar profile URL? (optional — leave blank to skip)\n   Example: https://scholar.google.com/citations?user=XXXXXXXXX&sortby=pubdate"

2. **arxiv categories** — "Which arxiv categories should I monitor? (comma-separated, default: cs.LG, cs.CL, cs.AI)\n   Full list: https://arxiv.org/category_taxonomy"

3. **Keywords** — "Any keywords to pre-filter papers by? Only papers containing at least one keyword will be analyzed. (comma-separated, leave blank to analyze all)\n   Example: causality, forecasting, diffusion"

4. **Ranking criteria** — "Describe in plain language what makes a paper exciting to you — this guides the relevance scoring.\n   Example: prioritize methods that improve sample efficiency in reinforcement learning"

5. **Top N** — "How many papers should appear in the final report? (default: 5)"

6. **Max papers to analyze** — "How many papers should Claude analyze per run? More = better coverage but slower. (default: 10)"

Once you have all answers, call `save_config` with the collected values. Skip any fields the user left blank (don't pass them — keep existing or default values).

After saving, confirm with a brief summary of what was set and tell the user they can now run `/scout` to fetch today's papers, or `/scout-setup` again to change any setting.
