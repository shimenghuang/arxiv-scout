"""
PreToolUse hook for store_analysis.

Intercepts the store_analysis MCP call, saves analysis_json to disk,
then strips the argument so Claude Code displays store_analysis() with nothing.
"""
import json
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CACHE_PATH = PROJECT_ROOT / "data" / ".analysis_cache.json"

try:
    data = json.load(sys.stdin)
    analysis = data.get("tool_input", {}).get("analysis_json")
    if analysis is not None:
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {}
        }
    }))
except Exception:
    # On any failure, let the call proceed normally
    print("{}")
