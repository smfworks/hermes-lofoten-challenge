"""Skill-forge plugin — registration.

Testing and validation tools for Hermes skills and plugins.
Provides four tools, a /forge slash command, and a post_tool_call
hook for execution timing.

Named after the blacksmith's forge at Saint Michael's Forge (SMF Works) —
where raw material is shaped, tested, and hardened before it ships.
"""

import json
import logging
import time
import threading
from pathlib import Path
import os

from . import schemas, tools

logger = logging.getLogger(__name__)

_timing_lock = threading.Lock()
_timing_data = []


def _on_post_tool_call(tool_name, args, result, task_id, duration_ms=0, **kwargs):
    """Hook: logs tool execution times for performance tracking."""
    try:
        with _timing_lock:
            _timing_data.append({
                "tool": tool_name,
                "duration_ms": duration_ms or 0,
                "timestamp": time.time(),
                "session": task_id,
            })
            # Keep last 1000 entries
            if len(_timing_data) > 1000:
                _timing_data.pop(0)

            # Persist periodically
            if len(_timing_data) % 20 == 0:
                _persist_timing()
    except Exception as e:
        logger.debug("skill-forge: post_tool_call hook error: %s", e)


def _persist_timing():
    """Persist timing data to disk."""
    try:
        home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
        forge_dir = Path(home) / "skill-forge"
        forge_dir.mkdir(parents=True, exist_ok=True)
        timing_file = forge_dir / "timing.json"

        # Aggregate stats
        from collections import defaultdict
        tool_stats = defaultdict(list)
        for entry in _timing_data:
            tool_stats[entry["tool"]].append(entry["duration_ms"])

        aggregated = {
            "total_calls": len(_timing_data),
            "per_tool": {
                tool: {
                    "calls": len(times),
                    "avg_ms": round(sum(times) / len(times), 2) if times else 0,
                    "min_ms": min(times) if times else 0,
                    "max_ms": max(times) if times else 0,
                }
                for tool, times in tool_stats.items()
            },
        }
        timing_file.write_text(json.dumps(aggregated, indent=2))
    except Exception:
        pass


def _handle_forge(raw_args: str) -> str:
    """Slash command: /forge — validates all installed skills."""
    try:
        raw = raw_args.strip()
        home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))

        if raw == "plugins":
            # Validate all plugins
            plugins_dir = Path(home) / "plugins"
            if not plugins_dir.exists():
                return "No plugins directory found."

            plugin_dirs = [d for d in plugins_dir.iterdir()
                          if d.is_dir() and (d / "plugin.yaml").exists()]

            lines = [f"🔨 **Skill Forge — Plugin Validation**", ""]
            total = 0
            valid = 0
            issues = 0

            for pd in sorted(plugin_dirs):
                total += 1
                result = tools.validate_plugin({"plugin": str(pd)})
                data = json.loads(result)
                if data.get("valid"):
                    valid += 1
                    lines.append(f"  ✅ {pd.name}")
                else:
                    issues += 1
                    lines.append(f"  ❌ {pd.name}: {', '.join(data.get('errors', []))}")

                warns = data.get("warnings", [])
                if warns:
                    lines.append(f"     ⚠️ {', '.join(warns[:2])}")

            lines.append(f"\n**Summary:** {valid}/{total} valid, {issues} with errors")
            return "\n".join(lines)

        # Default: validate all skills
        skills_dir = Path(home) / "profiles" / "nemo" / "skills"
        if not skills_dir.exists():
            return "No skills directory found."

        skill_files = list(skills_dir.rglob("SKILL.md"))
        lines = [f"🔨 **Skill Forge — Skill Validation ({len(skill_files)} skills)**", ""]
        total = 0
        valid = 0
        issues = 0

        for sf in sorted(skill_files):
            total += 1
            result = tools.validate_skill({"skill": str(sf)})
            data = json.loads(result)
            if data.get("valid"):
                valid += 1
            else:
                issues += 1
                errors = data.get("errors", [])
                lines.append(f"  ❌ {sf.parent.name}: {', '.join(errors)}")

            warns = data.get("warnings", [])
            if warns:
                if data.get("valid"):
                    # Only show warnings for valid skills (errors already shown)
                    for w in warns[:1]:
                        lines.append(f"  ⚠️ {sf.parent.name}: {w}")

        lines.append(f"\n**Summary:** {valid}/{total} valid, {issues} with errors")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Forge command failed: {e}"


def register(ctx):
    """Wire schemas to handlers and register hooks."""
    ctx.register_tool(
        name="validate_skill",
        toolset="skill_forge",
        schema=schemas.VALIDATE_SKILL,
        handler=tools.validate_skill,
    )

    ctx.register_tool(
        name="validate_plugin",
        toolset="skill_forge",
        schema=schemas.VALIDATE_PLUGIN,
        handler=tools.validate_plugin,
    )

    ctx.register_tool(
        name="test_tool_handler",
        toolset="skill_forge",
        schema=schemas.TEST_TOOL_HANDLER,
        handler=tools.test_tool_handler,
    )

    ctx.register_tool(
        name="stress_test_tool",
        toolset="skill_forge",
        schema=schemas.STRESS_TEST_TOOL,
        handler=tools.stress_test_tool,
    )

    # Hook for timing tracking
    ctx.register_hook("post_tool_call", _on_post_tool_call)

    # Slash command
    ctx.register_command(
        "forge",
        handler=_handle_forge,
        description="Validate all skills (/forge) or plugins (/forge plugins)",
    )

    logger.info("skill-forge: registered 4 tools, 1 hook, 1 command")