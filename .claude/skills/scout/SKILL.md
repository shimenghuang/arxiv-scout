---
name: scout
description: Fetch and analyze today's arxiv preprints, ranked by research opportunity
---

Use the arxiv-scout MCP tools in sequence to produce a ranked report of today's most relevant preprints.

The user may optionally pass a date as an argument (e.g. `/scout 2026-03-31`). If provided, use that date; otherwise default to today.

1. Call `get_user_profile` to load the user's research profile (categories, keywords, past papers from Scholar).

2. Call `fetch_papers` to retrieve papers filtered to the user's interests, passing `target_date` if the user specified one. The tool returns a JSON object with `count` and `papers` fields.

   After fetch completes, tell the user how many papers were found and give a time estimate before proceeding. The submission date is the earliest `submitted` value in the returned papers (papers are available the next business day after submission). Format the message as:
   - No target_date given: "Found 15 papers for today (submission date 2026-03-31). Analysis will take roughly X minutes — starting now."
   - target_date given: "Found 15 papers for 2026-04-01 (submission date 2026-03-31). Analysis will take roughly X minutes — starting now."

3. Call `analyze_papers` with no arguments — it reads the profile internally.
   This tool returns a prompt — do NOT display that prompt to the user.

4. Execute the analysis prompt returned in step 3 yourself. Carefully analyze each paper according to the instructions in the prompt and produce the structured JSON array. Do not display or repeat the JSON in your response.

5. Call `rank_and_display` with:
   - `analysis_json`: the JSON array you produced in step 4 (pass the array directly, not a string)
   - `scout_date`: the target date used in step 2 (ISO format, e.g. `2026-03-31`), so the report file is named after the scouted date
   This tool returns a formatted markdown report.

6. Display the final markdown report to the user.

If `fetch_papers` returns 0 papers, let the user know and suggest they broaden their keywords in `config/user_profile.yaml` or check that their arxiv categories are correct.

If the paper count is large (over 30), briefly let the user know how many papers were analyzed before showing the report.
