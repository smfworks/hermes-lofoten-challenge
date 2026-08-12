---
name: skill-radar
version: 1.0.0
category: productivity
tags:
  - skill-discovery
  - skills
  - hermes-cli
  - onboarding
  - gap-analysis
related_skills:
  - find-skills
  - hermes-agent
  - hermes-feature-selector
trigger: "When you need to discover, evaluate, or install skills to close a capability gap for a task. Use before building something new — a skill may already exist."
description: "Discover relevant skills for any task using hermes skills CLI commands. Inventory, search, browse, inspect, install, and evaluate skills. Decide when to search vs build."
---

# skill-radar — Adaptive Skill Discovery

> *Røst's seabird cliffs are one of the most biodiverse ecosystems in the Arctic. Hundreds of species — puffins, guillemots, kittiwakes, sea eagles — each adapted to a specific niche in a harsh environment. No single bird fills every role; the colony thrives because each species discovered its specialization. Likewise, no single agent skill covers every task. The agent's job is to scan the ecosystem, identify which skills fill the current gap, and adapt before building from scratch.*

## What This Skill Does

**skill-radar** teaches you to systematically discover skills relevant to a task using the `hermes skills` CLI. Instead of guessing or building from scratch, you inventory what's installed, search the hub, evaluate candidates, and install only what fits. When no skill exists, you build one — with full awareness of why the gap exists and what the new skill should cover.

## Quick Reference

| Action | Command |
|---|---|
| List installed skills | `hermes skills list` |
| Search the hub | `hermes skills search "keyword"` |
| Browse all available | `hermes skills browse` |
| Inspect before installing | `hermes skills inspect <id>` |
| Install a skill | `hermes skills install <id>` |

---

## Step-by-Step Workflow

### Step 1 — Inventory What You Already Have

Before searching externally, check what's already installed. The system prompt lists available skills, but use the CLI for a definitive check:

```bash
hermes skills list
```

This shows all skills currently installed in the active profile. Note the **category** and **tags** — they tell you the ecosystem's coverage. If a skill is already installed that covers your task, load it with `skill_view(name='<skill-name>')` and follow its instructions.

**Key insight**: The system prompt's `<available_skills>` block is your first radar sweep. It organizes skills by category. Scan it before reaching for the CLI.

### Step 2 — Analyze the Task to Identify Gaps

Before searching, articulate what you actually need. Ask:

1. **What domain does this task belong to?** (e.g., devops, data-science, research, creative, security)
2. **What capabilities are required?** (e.g., API calls, file parsing, deployment, code review, visualization)
3. **What capabilities do I already have?** (from Step 1)
4. **What's the gap?**

Write down the gap as specific keywords. These become your search queries.

**Example**:
- Task: "Set up a Minecraft modpack server"
- Domain: gaming
- Required: server provisioning, modpack installation, port management
- Already have: `docker-management` (devops), `minecraft-modpack-server` (gaming)
- Gap: None — `minecraft-modpack-server` already covers it. Load it.

**Counter-example**:
- Task: "Monitor RSS feeds for mentions of our company"
- Required: RSS parsing, feed monitoring, alerting
- Already have: nothing obviously relevant
- Gap: RSS/feed monitoring
- Action: Search for "rss", "feed", "monitor", "blogwatcher"

### Step 3 — Search the Skills Hub

Use targeted keywords from your gap analysis:

```bash
hermes skills search "rss"
hermes skills search "feed monitor"
hermes skills search "blog"
```

Search results show skill IDs, names, descriptions, and source (official/community). Run multiple searches with different keywords — skills are tagged variably, and a single keyword may miss relevant results.

**Search tips**:
- Use broad terms first ("deploy"), then narrow ("kubernetes", "helm")
- Try synonyms ("email" / "imap" / "smtp" / "mail")
- Search by tool name if you know it ("himalaya", "gh", "curl")
- Category names work too ("devops", "research", "creative")

### Step 4 — Browse When Search Isn't Enough

If targeted searches come up empty, browse the full catalog:

```bash
hermes skills browse
```

This shows all available skills organized by category. Use browsing when:
- You're unsure what keywords to use
- The task spans multiple domains
- You want to understand the ecosystem's coverage
- You're onboarding and want to know what's available

### Step 5 — Inspect Before Installing

Never install blindly. Always inspect:

```bash
hermes skills inspect <skill-id>
```

This shows the full skill metadata: description, trigger conditions, tags, related skills, and a preview of the SKILL.md content. Evaluate:

- **Does the trigger match my task?** The `trigger` field tells you when to use it.
- **Are the commands current?** Check if it references real CLI tools.
- **Is the workflow clear?** Good skills have numbered steps with exact commands.
- **Does it list pitfalls?** Quality skills document what can go wrong.
- **Are related skills better fits?** The `related_skills` field points to alternatives.

### Step 6 — Evaluate Skill Quality

Not all skills are equal. Use this hierarchy:

| Tier | Source | Trust Level | Notes |
|---|---|---|---|
| **Official** | NousResearch / hermes-agent repo | High | Maintained, tested, documented |
| **Community** | Third-party contributors | Medium | Check author, last update, stars |
| **Browse-shell** | `hermes skills browse` extras | Variable | Inspect carefully before installing |

**Quality signals**:
- ✅ Clear `trigger` field that matches a real use case
- ✅ Numbered steps with exact, copy-pasteable commands
- ✅ Pitfalls/gotchas section
- ✅ Verification steps (how to confirm it worked)
- ✅ `related_skills` cross-references
- ❌ Vague description with no trigger
- ❌ References non-existent tools or endpoints
- ❌ No error handling guidance
- ❌ Hardcoded paths or credentials

### Step 7 — Install

Once you've evaluated and chosen:

```bash
hermes skills install <skill-id>
```

After installation, load it immediately to verify:

```
skill_view(name='<skill-name>')
```

Then follow the skill's instructions.

---

## Skill Ecosystem Structure

Skills are organized by **categories**, **tags**, and **related_skills**:

### Categories
Top-level grouping by domain:
- `productivity` — documents, spreadsheets, project management
- `devops` — Docker, infrastructure, monitoring, deployments
- `research` — academic papers, web monitoring, market data
- `creative` — ASCII art, diagrams, design, music
- `mlops` — ML training, inference, evaluation
- `github` — repo management, PRs, code review
- `email` — mail clients, IMAP/SMTP
- `security` — OSINT, reconnaissance
- `gaming` — game servers, emulators
- `media` — YouTube, Spotify, GIFs, audio
- `note-taking` — Obsidian, second-brain
- `software-development` — debugging, TDD, planning
- `social-media` — X/Twitter, posting, monitoring
- `smart-home` — Hue lights, home automation
- `data-science` — Jupyter, data analysis
- `mcp` — Model Context Protocol servers

### Tags
Fine-grained labels within a category. Multiple tags per skill. Used by `hermes skills search` for matching.

### related_skills
Cross-references to skills in other categories that complement or overlap. Always check these — a skill in a different category may be a better fit.

---

## Decision Framework: Search vs Build

```
┌──────────────────────────────────────────────────────────────┐
│  TASK REQUIRES A CAPABILITY I DON'T HAVE                      │
│                                                               │
│  1. Check installed skills (skill_view, system prompt)        │
│     └─ Found? → Load and use it. Done.                        │
│                                                               │
│  2. Not found? → Search the hub                               │
│     hermes skills search "<keywords>"                         │
│     └─ Found? → Inspect → Evaluate → Install. Done.           │
│                                                               │
│  3. Search empty? → Browse full catalog                       │
│     hermes skills browse                                      │
│     └─ Found? → Inspect → Evaluate → Install. Done.           │
│                                                               │
│  4. Nothing exists? → BUILD A NEW SKILL                       │
│     └─ Is the task complex (5+ steps, recurring)?             │
│        ├─ YES → Create a SKILL.md (see below)                 │
│        └─ NO  → Just do the task inline. No skill needed.     │
└──────────────────────────────────────────────────────────────┘
```

### When to Search
- The task is in a known domain (devops, research, etc.)
- You suspect a tool exists but don't know the skill name
- You're new to the ecosystem and want to understand coverage
- The task is common enough that someone likely built a skill for it

### When to Build
- Multiple searches and browsing confirm no skill exists
- The task is complex (5+ steps) and likely to recur
- You've discovered a workflow that would benefit others
- The existing skills are close but miss a critical capability

### How to Create a New Skill

When you've confirmed a gap, create a skill:

1. **Choose a name** — lowercase, hyphenated, descriptive (e.g., `rss-aggregator`)
2. **Create the SKILL.md file**:
   ```
   skill_manage(action='create', name='rss-aggregator', content='...')
   ```
3. **Include in the SKILL.md**:
   - YAML frontmatter: `name`, `version`, `category`, `tags`, `related_skills`, `trigger`, `description`
   - `trigger` field: one sentence describing when to use this skill (must be self-contained in first 57 chars for the system prompt index)
   - Numbered steps with exact commands
   - Pitfalls section
   - Verification steps
4. **Test it** — follow your own instructions to verify they work
5. **Iterate** — if you hit issues while using the skill, patch it immediately with `skill_manage(action='patch')`

**Skill quality checklist**:
- [ ] Trigger is specific and self-contained
- [ ] Steps are numbered with exact commands
- [ ] Commands are tested and working
- [ ] Pitfalls section covers known issues
- [ ] Verification step confirms success
- [ ] `related_skills` cross-references are valid

---

## Common Pitfalls

1. **Don't skip the inventory step.** The skill you need may already be installed. Always check `hermes skills list` and the system prompt's `<available_skills>` block first.

2. **Don't install without inspecting.** `hermes skills inspect <id>` reveals quality, compatibility, and whether the trigger matches your task.

3. **Don't search with a single keyword.** Skills are tagged variably. Run 2-3 searches with different terms before concluding nothing exists.

4. **Don't ignore `related_skills`.** A skill in a different category may be a better fit. Always check cross-references.

5. **Don't build before searching thoroughly.** The ecosystem is large and growing. Three searches + one browse pass is the minimum before building.

6. **Don't forget to load after installing.** Installation makes a skill available but doesn't load its instructions. Call `skill_view(name='<skill-name>')` to actually read and follow it.

7. **Don't create skills for one-off tasks.** Skills are for recurring, multi-step workflows. If the task is simple and won't recur, just do it.

8. **Don't let skills go stale.** If you use a skill and find wrong commands or missing steps, patch it immediately with `skill_manage(action='patch')`.

---

## The Lofoten Connection

Røst, the southernmost tip of the Lofoten archipelago, hosts Norway's largest seabird cliffs — a towering ecosystem where hundreds of species coexist by specialization. Puffins dive for sand eels, guillemots chase fish underwater, kittiwakes nest on narrow ledges, sea eagles patrol from above. Each species *discovered* its niche through evolutionary adaptation to the harsh Arctic environment.

**skill-radar** embodies this adaptive discovery. An agent facing a new task is like a seabird encountering a changing Arctic — the old strategies may not work, and survival depends on finding the right adaptation quickly. The `hermes skills` ecosystem is the cliff face: dense with specialized skills, each evolved for a specific niche. The agent's job is to scan (search), evaluate (inspect), and adopt (install) the right specialization — or, when no existing skill fits, evolve a new one (create).

Just as Røst's biodiversity makes the colony resilient, a rich skill ecosystem makes the agent resilient. The agent that discovers and adapts thrives; the one that ignores the ecosystem and tries to build everything from scratch wastes energy and misses proven solutions.

*Team Røst — Adaptive Discovery. SMF Works Lofoten Challenge.*