---
name: scout
description: Fetch and analyze today's arxiv preprints, ranked by research opportunity
---

Use the arxiv-scout MCP tools in sequence to produce a ranked report of today's most relevant preprints.

The user may optionally pass a date as an argument (e.g. `/scout 2026-03-31`). If provided, use that date; otherwise default to today.

1. Call `get_user_profile` to load the user's research profile (categories, keywords, past papers from Scholar).

2. Call `fetch_papers` to retrieve papers filtered to the user's interests, passing `target_date` if the user specified one. The tool returns a JSON object with `count` and `papers` fields.

   After fetch completes, tell the user how many papers were found and give a time estimate before proceeding. Use the target_date (or "today" if none was specified) — do NOT use the papers' submitted dates. Example: "Found 15 papers for today. Analysis will take roughly 2–3 minutes — starting now."

3. Call `analyze_papers` with no arguments — it reads the profile internally.
   This tool returns a prompt — do NOT display that prompt to the user.

4. Execute the analysis prompt returned in step 3 yourself. Carefully analyze each paper according to the instructions in the prompt and produce the structured JSON array. Write it to `data/.analysis_cache.json` using the Write tool — serialize it as **compact JSON with no indentation** (a single line). Do not display or repeat the JSON in your response.

5. Call `rank_and_display` with:
   - `scout_date`: the target date used in step 2 (ISO format, e.g. `2026-03-31`), so the report file is named after the scouted date
   This tool returns a formatted markdown report.

6. Display the final markdown report to the user.

If `fetch_papers` returns 0 papers, let the user know and suggest they broaden their keywords in `config/user_profile.yaml` or check that their arxiv categories are correct.

If the paper count is large (over 30), briefly let the user know how many papers were analyzed before showing the report.
