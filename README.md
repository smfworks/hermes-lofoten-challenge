# Hermes Lofoten Challenge

> New skills and plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — built during a team engineering sprint inspired by the Lofoten Islands of Norway.

## The Challenge

While our principal traveled from Oslo to the Lofoten Islands, the SMF Works AI team conducted a wide-ranging engineering sprint: assess Hermes as a platform, research Lofoten in depth, and build new skills and plugins that meaningfully extend the platform.

## Teams and Artifacts

### Team Maelstrom — Tool Telemetry & Self-Diagnostics

Named for the **Moskstraumen**, the Lofoten maelstrom that gave the world the word "maelstrom." Just as that tidal current system makes invisible forces visible as surface patterns, this team's work makes invisible tool usage patterns visible and diagnosable.

| Artifact | Type | Description |
|----------|------|-------------|
| [hermes-plugin-tool-telemetry](team-maelstrom/hermes-plugin-tool-telemetry/) | Plugin | Passive tool call telemetry — records every tool invocation with redacted args, duration, and success status into a local SQLite database. Exposes `telemetry_summary`, `telemetry_failures`, `telemetry_export` tools. 41 tests, all passing. |
| [agent-self-diagnostic](team-maelstrom/agent-self-diagnostic/) | Skill | Structured clinical diagnostic protocol for agents to assess their own health using telemetry data. Observe → assess → classify → recommend. |

### Team Stockfish — Skill Gap Analysis & Collaboration

Named for **stockfish (tørrfisk)**, the air-dried cod that has been Lofoten's primary export for over 1,000 years. Viking Age cod bones from Lofoten have been found in Haithabu, Germany (800–1066 AD), proving a stockfish trade network stretching over 1,000 miles. Just as stockfish production involves examining each fish for quality, this team's work examines the skill library for gaps and quality issues.

| Artifact | Type | Description |
|----------|------|-------------|
| [hermes-plugin-skill-gap-analyzer](team-stockfish/hermes-plugin-skill-gap-analyzer/) | Plugin | Analyzes the skill library for coverage gaps, duplicates, and quality issues. Exposes `skill_gap_scan`, `skill_gap_report`, `skill_similarity` tools. 77 tests, all passing. |
| [cross-agent-collaboration](team-stockfish/cross-agent-collaboration/) | Skill | Multi-agent collaboration protocols — delegate_task patterns, cross-profile communication, coordination patterns, conflict resolution. |

### Team Norddal — Fleet Pulse

Named for **Norddal**, a historic fjord-side settlement on Eidsfjorden. Fleet activity monitoring across all Hermes profiles.

| Artifact | Type | Description |
|----------|------|-------------|
| [fleet-pulse](team-norddal/plugin/) | Plugin | Tracks session lifecycle and tool usage across all Hermes profiles. Exposes `/fleet-pulse` slash command. |
| [fleet-ops](team-norddal/skill/) | Skill | Fleet operations coordination skill. |

### Team Røst — Context Bridge

Named for **Røst**, the southernmost island in the Lofoten archipelago, where Italian merchant Pietro Querini was stranded in 1432 and brought stockfish back to Venice. Context preservation across session resets.

| Artifact | Type | Description |
|----------|------|-------------|
| [context-bridge](team-rost/plugin/) | Plugin | Preserves context across session resets by saving snapshots. Exposes `/context-bridge` slash command. |
| [skill-radar](team-rost/skill/) | Skill | Skill discovery and awareness skill. |

### Team Svolvær — Cost Watch

Named for **Svolvær**, the administrative center of Vesterålen/Lofoten and the largest town in the archipelago. API cost tracking per session and profile.

| Artifact | Type | Description |
|----------|------|-------------|
| [cost-watch](team-svolvaer/plugin/) | Plugin | Tracks API costs per session and profile using post_api_request hooks. |
| [session-analytics](team-svolvaer/skill/) | Skill | Session analytics and insights skill. |

## Lofoten Research

The research that informed this sprint is in [`research/lofoten-research.md`](research/lofoten-research.md) — a comprehensive document covering geology (2-billion-year-old rock), geography (7 main islands, 175km archipelago), climate, biodiversity, 7,000 years of human settlement, the stockfish trade, Norse and Sámi influences, the Moskstraumen maelstrom, and modern challenges.

## Production testing

Automated tests exist for two plugins. They **must be run in isolated processes** because each plugin is a module named `__init__.py`. A single `pytest` collection over the repo imports the wrong plugin and fails ~73 tests that pass in isolation.

```bash
chmod +x scripts/test.sh
./scripts/test.sh
```

CI (GitHub Actions) runs each suite as its own job. See CONTRIBUTING.md.

Honest status: telemetry 41/41 isolated; skill-gap-analyzer 77/77 isolated. Other team plugins have writeups (`test-report.md`) but no automated suite yet.

## License

MIT