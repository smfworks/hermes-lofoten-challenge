"""Session-observability plugin — registration.

Passive observability for Hermes Agent sessions. Tracks tool usage, response
times, error rates, and session health. Provides two tools (session_report,
session_health) and a /session-stats slash command.

Inspired by the Lofoten lighthouses — silent sentinels that watch without
interfering, providing guidance when conditions deteriorate.
"""

import json
import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def _on_post_tool_call(tool_name, args, result, task_id, duration_ms=0, **kwargs):
    """Hook: runs after every tool call — records metrics."""
    try:
        tools.record_tool_call(
            tool_name=tool_name,
            args=args,
            result=result,
            task_id=task_id,
            duration_ms=duration_ms or 0,
        )
    except Exception as e:
        logger.debug("session-observability: post_tool_call hook error: %s", e)


def _on_session_start(session_id, **kwargs):
    """Hook: runs when a new session starts."""
    try:
        tools.session_start(session_id=session_id)
    except Exception as e:
        logger.debug("session-observability: session_start hook error: %s", e)


def _on_session_end(session_id, completed=False, **kwargs):
    """Hook: runs when a session ends."""
    try:
        tools.session_end(session_id=session_id)
    except Exception as e:
        logger.debug("session-observability: session_end hook error: %s", e)


def _handle_session_stats(raw_args: str) -> str:
    """Slash command: /session-stats — shows quick session summary."""
    fmt = "detailed" if raw_args.strip() == "detailed" else "summary"
    result = tools.session_report({"format": fmt})
    try:
        data = json.loads(result)
        if "error" in data:
            return f"❌ {data['error']}"

        lines = []
        lines.append(f"📊 **Session Observability Report**")
        lines.append(f"")
        lines.append(f"**Session:** {data.get('session_id', 'unknown')}")
        lines.append(f"**Status:** {data.get('status', 'unknown')}")
        lines.append(f"**Duration:** {data.get('duration_seconds', 'N/A')}s")
        lines.append(f"**Tool calls:** {data.get('total_tool_calls', 0)}")
        lines.append(f"**Errors:** {data.get('error_count', 0)} ({data.get('error_rate_percent', 0)}%)")
        lines.append(f"")

        tools_used = data.get("tools_used", {})
        if tools_used:
            lines.append("**Tools used:**")
            for tool, count in sorted(tools_used.items(), key=lambda x: -x[1]):
                lines.append(f"  • {tool}: {count}")

        if fmt == "detailed":
            per_tool = data.get("per_tool_breakdown", {})
            if per_tool:
                lines.append(f"\n**Per-tool breakdown:**")
                for tool, stats in sorted(per_tool.items()):
                    lines.append(
                        f"  • {tool}: {stats['calls']} calls, "
                        f"{stats['error_rate']}% errors, "
                        f"{stats['avg_duration_ms']}ms avg"
                    )

        lines.append(f"\n**Global:** {data.get('global_total_sessions', 0)} sessions, "
                     f"{data.get('global_total_tool_calls', 0)} total calls")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to format report: {e}"


def register(ctx):
    """Wire schemas to handlers and register hooks."""
    ctx.register_tool(
        name="session_report",
        toolset="session_observability",
        schema=schemas.SESSION_REPORT,
        handler=tools.session_report,
    )

    ctx.register_tool(
        name="session_health",
        toolset="session_observability",
        schema=schemas.SESSION_HEALTH,
        handler=tools.session_health,
    )

    # Hooks — passive observers, never block the agent
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)

    # Slash command for quick access
    ctx.register_command(
        "session-stats",
        handler=_handle_session_stats,
        description="Show session observability stats (use 'detailed' for full breakdown)",
    )

    logger.info("session-observability: registered 2 tools, 3 hooks, 1 command")