# Team Norddal — Oppositional Test Report

## Plugin: fleet-pulse

### Test Coverage

| Test | Description | Result |
|------|-------------|--------|
| Python syntax | `ast.parse()` on __init__.py | ✅ PASS |
| YAML manifest | `yaml.safe_load()` on plugin.yaml, verify hooks | ✅ PASS |
| Module import | Import as Python module, check all functions exist | ✅ PASS |
| Hook execution | Simulate session start, tool calls, session end with temp HERMES_HOME | ✅ PASS |
| Slash command | Test all subcommands: overview, detail, log, help, reset | ✅ PASS |
| Empty fleet | No data file exists — should show "No activity" message | ✅ PASS |
| Corrupted JSON | Write invalid JSON to activity.json — hooks should recreate data | ✅ PASS |
| Concurrent access | 5 threads × 20 tool calls simultaneously — no data loss | ✅ PASS (100/100 calls recorded) |
| Missing HERMES_HOME | No env var set — should default to ~/.hermes | ✅ PASS |
| Reset protection | Reset without --confirm must NOT delete data | ✅ PASS (fixed — initial version had bug) |
| 50 profile stress | Create 50 profiles, verify overview renders | ✅ PASS |
| Empty/None tool names | Empty string and None tool_name should not crash | ✅ PASS |
| None args to hooks | None session_id, source, completed, interrupted | ✅ PASS |
| Unusual HERMES_HOME paths | Various path formats | ✅ PASS |
| Log with no file | No log file exists — should show "empty" message | ✅ PASS |
| Detail non-existent profile | Should show "not found" + available profiles | ✅ PASS |
| Invalid log number | "log abc" should show "Invalid number" | ✅ PASS |

### Bugs Found and Fixed

1. **Reset without --confirm would reset immediately** — The original logic `if len(argv) >= 2 and argv[1] != "--confirm"` would pass through to `_reset_data()` when called with no arguments (len < 2). Fixed to `if "--confirm" not in argv[1:]` which correctly blocks reset in all cases except when --confirm is explicitly present.

### Hardening Notes

- All file I/O wrapped in try/except with logging — never crashes the agent loop
- Thread-safe via `threading.Lock()` on all data read/write operations
- Atomic file writes (write to .tmp then `replace()`) — no partial data
- Corrupted JSON handled gracefully — `_load_activity()` returns empty structure
- All hook callbacks accept `**_` kwargs — forward-compatible with new hook args
- No external dependencies — pure stdlib (json, os, threading, datetime, pathlib)

### Lofoten Connection

The plugin is inspired by the Lofotfisket — the seasonal cod fishery (February–April) where the entire Lofoten fishing fleet coordinates to maximize the collective catch. Every boat knows where the others are, what they're catching, and when they're active. This plugin brings that same fleet-wide awareness to Hermes: any agent can see what every profile is doing, what tools they're using, and when they were last active.

## Skill: fleet-ops

The skill is a documentation/skill file (SKILL.md) — no executable code to test. Verified:
- YAML frontmatter is valid
- All documented commands are real Hermes CLI commands
- Fleet roster matches actual profile configuration
- Integration section correctly references the fleet-pulse plugin

### Test approach for skill:
- Verified all `hermes` CLI commands referenced in the skill exist in the hermes-agent skill
- Verified the fleet roster matches `hermes profile list` output
- Verified the gateway management commands match the systemd service naming convention
- Verified the skill discovery and installation instructions match the hermes-agent skill documentation