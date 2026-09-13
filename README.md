# Hermes Lofoten Challenge

**Public catalog** of SMF Works’ Lofoten-sprint Hermes skills and plugins.

Outsiders should not have to bounce across a dozen sibling repos to learn what exists, what is installable, and what is experimental, mock, or empty. This repository is the map. In-repo Maelstrom/Stockfish (and later-team) artifacts stay here; sibling repos stay where they are.

This is **not** upstream [Hermes Agent](https://github.com/NousResearch/hermes-agent). We do not rewrite Hermes.

Inventory verified **2026-09-13** via the GitHub API (`GET /users/smfworks/repos`). Status and install hints come from those repos’ READMEs and in-tree manifests — not invented stars or metrics.

---

## Start here

Three entries have the clearest documented install path and an honest job to do:

| If you want to… | Use | Why this one |
|-----------------|-----|----------------|
| See what is actually on a Hermes home | [`hermes-plugin-fjord-audit`](https://github.com/smfworks/hermes-plugin-fjord-audit) | Separate repo. README calls **1.1.0** a production-ready pass. Filesystem-only audit (skills, memory, plugins, profiles, config). |
| Watch tool-call health | [tool-telemetry](team-maelstrom/hermes-plugin-tool-telemetry/) (this monorepo) | Shipped here. Isolated pytest in CI. Pairs with the [agent-self-diagnostic](team-maelstrom/agent-self-diagnostic/) skill. |
| Author or gate a new extension | [`hermes-extension-forge`](https://github.com/smfworks/hermes-extension-forge) | Separate repo. `extension-forge` skill + `hermes-publish-assistant` plugin. Point new work here, not at a fresh ungoverned repo. |

Otherwise **pick by need** using the filters below. Do not install everything.

### Pick by need

| Need | Filter |
|------|--------|
| Observability / cost / fleet | In-repo: tool-telemetry, session-observability, fleet-pulse, cost-watch |
| Skill library quality | In-repo: skill-gap-analyzer, skill-radar, skill-forge (validator plugin) |
| Research / citations / writing | Sibling: stockfish-packet. In-repo: knowledge-atlas, research-synthesis |
| Multi-agent routing | Sibling: harbor (solo/pair/swarm), hybrid-routing (model/egress). In-repo: cross-agent-collaboration |
| Ship-quality gates | Sibling: maelstrom-gate, extension-forge. In-repo: oppositional-review |
| Resilience / eval playbooks | Sibling: hermes-skill-resilience-harness |
| Visual demos only | Sibling: hermes-skill-forge, hermes-mission-control — both **mock UIs** |
| Empty placeholders | `lofoten-challenge`, `hermes-skill-saga-memory` — public, **no files** |

---

## Status legend

| Status | Meaning |
|--------|---------|
| **Shipped in this monorepo** | Code lives in this repo. Copy/enable locally. |
| **Separate repo** | Standalone public repo with files. |
| **Experimental** | Sprint-grade skill, harness, or plugin. Useful, not a polished product. |
| **Mock** | Demo UI. Does not connect to a live Hermes instance. |
| **Empty** | Public repo exists; GitHub reports no contents. Treat as dead until someone fills it. Do not un-archive or delete siblings. |

`install` is not `enable`. Sibling plugins that document `hermes plugins install` still need `hermes plugins enable <name>` (or `--enable`).

---

## Catalog

### In this monorepo

| Name | Type | Purpose | Status | Install hint |
|------|------|---------|--------|--------------|
| [tool-telemetry](team-maelstrom/hermes-plugin-tool-telemetry/) | Plugin | Passive tool-call telemetry (redacted args, duration, success) into local SQLite. Tools: `telemetry_summary`, `telemetry_failures`, `telemetry_export`. | Shipped in this monorepo (isolated pytest in CI) | `cp -r team-maelstrom/hermes-plugin-tool-telemetry ~/.hermes/plugins/tool-telemetry` then `hermes config set plugins.enabled '["tool-telemetry"]'` — see [plugin README](team-maelstrom/hermes-plugin-tool-telemetry/README.md) |
| [agent-self-diagnostic](team-maelstrom/agent-self-diagnostic/) | Skill | Observe → assess → classify → recommend using telemetry (or session fallback). | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/agent-self-diagnostic/` |
| [skill-gap-analyzer](team-stockfish/hermes-plugin-skill-gap-analyzer/) | Plugin | Scan the skill library for thin categories, narrow skills, missing capabilities, overlaps. | Shipped in this monorepo (isolated pytest in CI) | `cp -r team-stockfish/hermes-plugin-skill-gap-analyzer ~/.hermes/plugins/skill-gap-analyzer` then enable — see [plugin README](team-stockfish/hermes-plugin-skill-gap-analyzer/README.md) |
| [cross-agent-collaboration](team-stockfish/cross-agent-collaboration/) | Skill | Multi-agent protocols: `delegate_task`, handoffs, conflict resolution. | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/cross-agent-collaboration/` |
| [knowledge-atlas](team-aurora/plugin/) | Plugin | Local JSON knowledge graph; extract/query entities from text. | Shipped in this monorepo (writeup tests only; no isolated pytest in CI) | Copy `team-aurora/plugin` to `~/.hermes/plugins/knowledge-atlas` and enable `knowledge-atlas` |
| [research-synthesis](team-aurora/skill/) | Skill | Turn raw research into cited writing (stockfish-style cure). | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/research-synthesis/` |
| [session-observability](team-nordfjord/plugin/) | Plugin | Passive session metrics, health score, `/session-stats`. | Shipped in this monorepo (writeup tests only) | Copy `team-nordfjord/plugin` to `~/.hermes/plugins/session-observability` and enable |
| [agent-self-assessment](team-nordfjord/skill/) | Skill | Honest capability / gap self-review (`sjølkritikk`). | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/agent-self-assessment/` |
| [skill-forge](team-skrotvagen/plugin/) (validator) | Plugin | Validate skills/plugins and stress-test tool handlers. **Not** the mock UI repo. | Shipped in this monorepo (writeup tests only) | Copy `team-skrotvagen/plugin` to `~/.hermes/plugins/skill-forge` and enable |
| [oppositional-review](team-skrotvagen/skill/) | Skill | Break your own work before shipping. | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/oppositional-review/` |
| [fleet-pulse](team-norddal/plugin/) | Plugin | Session/tool activity across Hermes profiles. Slash: `/fleet-pulse`. | Shipped in this monorepo (writeup tests only) | Copy `team-norddal/plugin` to `~/.hermes/plugins/fleet-pulse` and enable |
| [fleet-ops](team-norddal/skill/) | Skill | Fleet roster, dispatch, and cross-profile coordination. | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/fleet-ops/` |
| [context-bridge](team-rost/plugin/) | Plugin | Snapshot/restore context across session resets. Slash: `/context-bridge`. | Shipped in this monorepo (writeup tests only) | Copy `team-rost/plugin` to `~/.hermes/plugins/context-bridge` and enable |
| [skill-radar](team-rost/skill/) | Skill | Discover, inspect, and install skills via `hermes skills` before building new ones. | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/skill-radar/` |
| [cost-watch](team-svolvaer/plugin/) | Plugin | API cost tracking per session/profile (`post_api_request`). | Shipped in this monorepo (writeup tests only) | Copy `team-svolvaer/plugin` to `~/.hermes/plugins/cost-watch` and enable |
| [session-analytics](team-svolvaer/skill/) | Skill | Session patterns, token/cost trends, weekly review. | Shipped in this monorepo | Copy the directory to `~/.hermes/skills/session-analytics/` |

Team writeups live in each `team-*/test-report.md`. Only **tool-telemetry** and **skill-gap-analyzer** have isolated automated suites in this repo’s CI. See [Production testing](#production-testing).

### Sibling Lofoten repos (smfworks)

| Repo | Type | Purpose | Status | Install hint (from that README) |
|------|------|---------|--------|--------------------------------|
| [lofoten-challenge](https://github.com/smfworks/lofoten-challenge) | (placeholder) | GitHub description: fleet coordination, session analytics, adaptive discovery — those artifacts actually live **in this monorepo**. | **Empty** (API: no contents) | None. Do not clone expecting code. |
| [hermes-extension-forge](https://github.com/smfworks/hermes-extension-forge) | Tooling (skill + plugin) | Governed publish gates, docs standards, oppositional “breaker” review. Bundles `extension-forge` + `hermes-publish-assistant`. **No root README.** | Separate repo · experimental (manual install; CLI install commented as future) | From `hermes-publish-assistant/README.md`: copy that directory to `~/.hermes/plugins/hermes-publish-assistant/` then `hermes plugins enable hermes-publish-assistant`. Skill: `extension-forge`. |
| [hermes-skill-saga-memory](https://github.com/smfworks/hermes-skill-saga-memory) | Skill | GitHub description: narrative / place-based context (Norse / village knowledge). | **Empty** (API: no contents) | None. Description only. |
| [hermes-skill-resilience-harness](https://github.com/smfworks/hermes-skill-resilience-harness) | Skill | Trajectory eval, oppositional probes, recovery playbooks (maelstrom / stockfish checkpoints). Has `SKILL.md` + `references/`. | Separate repo · experimental | Skill README: `hermes -s hermes-resilience-harness` or `/skill hermes-resilience-harness` after the skill is on the profile. Or copy the repo into `~/.hermes/skills/hermes-resilience-harness/`. |
| [hermes-plugin-stockfish-packet](https://github.com/smfworks/hermes-plugin-stockfish-packet) | Plugin | Grounded research packets with claim–citation checks and a heuristic oppositional pass. Grades: rotten / wet / curing / stockfish. | Separate repo (README: **1.1.0**) | `hermes plugins install smfworks/hermes-plugin-stockfish-packet` then `hermes plugins enable stockfish-packet` |
| [hermes-plugin-fjord-audit](https://github.com/smfworks/hermes-plugin-fjord-audit) | Plugin | Structural audit of a Hermes home: sprawl, memory budgets, plugins, profiles, graded score. No network, no LLM. | Separate repo (README: **1.1.0**, production-ready pass) | `hermes plugins install smfworks/hermes-plugin-fjord-audit` then `hermes plugins enable fjord-audit` |
| [hermes-plugin-maelstrom-gate](https://github.com/smfworks/hermes-plugin-maelstrom-gate) | Plugin | Oppositional ship gate for skills/plugins (lint + pytest time-box). Needs PyYAML. | Separate repo (README: **1.1.0**) | `hermes plugins install smfworks/hermes-plugin-maelstrom-gate` then `hermes plugins enable maelstrom-gate` |
| [hermes-plugin-harbor](https://github.com/smfworks/hermes-plugin-harbor) | Plugin | Advisory solo / pair / swarm router. No hooks (cache-safe). Bundles `collaboration-pattern-router` skill. | Separate repo (plugin.yaml **1.2.0**; README documents pytest + self-test) | `hermes plugins install smfworks/hermes-plugin-harbor --enable` |
| [hermes-plugin-hybrid-routing](https://github.com/smfworks/hermes-plugin-hybrid-routing) | Plugin | Local classifier: sensitivity / role / difficulty → model + egress recommendation. Does **not** swap the session model. Blank model fields until you configure them. | Separate repo | `hermes plugins install smfworks/hermes-plugin-hybrid-routing` then `hermes plugins enable hybrid-contextual-routing`. Then copy and fill `routing_config.yaml` — see that README. |
| [hermes-skill-forge](https://github.com/smfworks/hermes-skill-forge) | Tooling (UI) | Next.js “studio” for skill lineages. | **Mock** — README: in-memory generator; **does not connect to Hermes**, does not persist, does not steer an agent. | `npm ci && npm run dev` (demo only) |

### Other Lofoten-window repo (not a skill/plugin)

| Repo | Type | Purpose | Status | Install hint |
|------|------|---------|--------|--------------|
| [hermes-mission-control](https://github.com/smfworks/hermes-mission-control) | Tooling (UI) | Dashboard for a mock agent swarm. Contemporaneous with skill-forge; **not** Lofoten-labeled in its description. | **Mock** — README: all data from `src/lib/mock-data.ts`; no live Hermes adapter | `npm ci && npm run dev` (demo only) |

---

## What this catalog is not

These public smfworks Hermes repos exist and were **left out on purpose** — they are not Lofoten-sprint skills/plugins:

- [hermes-agent](https://github.com/smfworks/hermes-agent) (upstream fork)
- [hermes-agent-self-evolution](https://github.com/smfworks/hermes-agent-self-evolution) (fork)
- [hermes-ai-team](https://github.com/smfworks/hermes-ai-team) (multi-agent operating guide)
- [hermes-omarchy](https://github.com/smfworks/hermes-omarchy), [smf-hermes](https://github.com/smfworks/smf-hermes) (desktop/Omarchy integration)
- [wisdomforge-kids-Hermes-profiles](https://github.com/smfworks/wisdomforge-kids-Hermes-profiles)

Empty sibling repos stay listed so nobody treats a GitHub description as a download.

---

## Teams and in-repo artifacts

The sprint ran while the principal traveled Oslo → Lofoten. Teams named themselves after places and crafts in the archipelago. Those deliverables remain in this tree.

### Team Maelstrom — tool telemetry & self-diagnostics

Named for the **Moskstraumen**. Invisible tool-call currents become visible patterns.

| Artifact | Type | Notes |
|----------|------|--------|
| [hermes-plugin-tool-telemetry](team-maelstrom/hermes-plugin-tool-telemetry/) | Plugin | Local SQLite; hooks only observe. |
| [agent-self-diagnostic](team-maelstrom/agent-self-diagnostic/) | Skill | Clinical protocol over telemetry. |

### Team Stockfish — skill gaps & collaboration

Named for **tørrfisk** (air-dried cod), Lofoten’s long-distance export. Quality-grade the library; coordinate the fleet.

| Artifact | Type | Notes |
|----------|------|--------|
| [hermes-plugin-skill-gap-analyzer](team-stockfish/hermes-plugin-skill-gap-analyzer/) | Plugin | Coverage, duplicates, recommendations. |
| [cross-agent-collaboration](team-stockfish/cross-agent-collaboration/) | Skill | Delegation and handoff protocols. |

### Team Aurora — knowledge & writing

| Artifact | Type | Notes |
|----------|------|--------|
| [knowledge-atlas](team-aurora/plugin/) | Plugin | Pattern-based entity graph (no NLP deps). |
| [research-synthesis](team-aurora/skill/) | Skill | Research → cited draft pipeline. |

### Team Nordfjord — session health

| Artifact | Type | Notes |
|----------|------|--------|
| [session-observability](team-nordfjord/plugin/) | Plugin | `/session-stats`, `session_report`, `session_health`. |
| [agent-self-assessment](team-nordfjord/skill/) | Skill | Capability inventory and gap review. |

### Team Skrotvågen — oppositional review

| Artifact | Type | Notes |
|----------|------|--------|
| [skill-forge](team-skrotvagen/plugin/) | Plugin | `validate_skill`, `validate_plugin`, stress tests. Distinct from the mock [hermes-skill-forge](https://github.com/smfworks/hermes-skill-forge) UI. |
| [oppositional-review](team-skrotvagen/skill/) | Skill | Adversarial self-review before publish. |

### Team Norddal — fleet pulse

Named for **Norddal** on Eidsfjorden.

| Artifact | Type | Notes |
|----------|------|--------|
| [fleet-pulse](team-norddal/plugin/) | Plugin | Cross-profile activity. |
| [fleet-ops](team-norddal/skill/) | Skill | Roster and dispatch. |

### Team Røst — context & discovery

Named for **Røst**, southernmost Lofoten.

| Artifact | Type | Notes |
|----------|------|--------|
| [context-bridge](team-rost/plugin/) | Plugin | Snapshots across reset. |
| [skill-radar](team-rost/skill/) | Skill | Search vs build. |

### Team Svolvær — cost watch

Named for **Svolvær**.

| Artifact | Type | Notes |
|----------|------|--------|
| [cost-watch](team-svolvaer/plugin/) | Plugin | Token/API cost per session and profile. |
| [session-analytics](team-svolvaer/skill/) | Skill | Patterns and reviews. |

---

## Lofoten research

Sprint research (not an installable extension) is in [`research/lofoten-research.md`](research/lofoten-research.md) — geology, geography, climate, biodiversity, settlement, the stockfish trade, Norse and Sámi influences, the Moskstraumen, and modern pressures. Companion notes: [`research/lofoten-research-nemo.md`](research/lofoten-research-nemo.md).

---

## Production testing

Automated tests exist for two in-repo plugins. They **must be run in isolated processes** because each plugin is a module named `__init__.py`. A single `pytest` collection over the repo imports the wrong plugin and fails tests that pass in isolation.

```bash
chmod +x scripts/test.sh
./scripts/test.sh
```

CI (GitHub Actions) runs each suite as its own job. See [CONTRIBUTING.md](CONTRIBUTING.md).

Honest status: telemetry and skill-gap-analyzer pass in isolation (run `./scripts/test.sh` for the current counts). Other team plugins have writeups (`test-report.md`) but no automated suite in this CI yet. Sibling repos keep their own CI — believe *their* READMEs, not this paragraph.

---

## New extensions

Do **not** add another ★0 sprint repo by default. Scaffold and gate new skills/plugins through [`hermes-extension-forge`](https://github.com/smfworks/hermes-extension-forge), then open a PR that updates **this** catalog if the thing is public and Lofoten-family.

Details: [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
