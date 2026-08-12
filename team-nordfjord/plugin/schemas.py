"""Tool schemas for session-observability plugin — what the LLM sees."""

SESSION_REPORT = {
    "name": "session_report",
    "description": (
        "Generate a report on the current session's observability metrics. "
        "Shows tool call counts, success/error rates, timing breakdowns, "
        "and session duration. Use this when asked about session performance, "
        "what tools were used, or how the session went."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "description": "Output format: 'summary' (default) or 'detailed'",
                "enum": ["summary", "detailed"],
            },
        },
        "required": [],
    },
}

SESSION_HEALTH = {
    "name": "session_health",
    "description": (
        "Check the current session's health. Returns a health score (0-100), "
        "active warnings (e.g., high error rate, slow responses), and "
        "recommendations. Use this to proactively detect degraded sessions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "threshold": {
                "type": "number",
                "description": "Health score threshold below which to emit warnings (default: 60)",
            },
        },
        "required": [],
    },
}