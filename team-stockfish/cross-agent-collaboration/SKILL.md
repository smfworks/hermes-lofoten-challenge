---
name: cross-agent-collaboration
description: "Use when coordinating multiple Hermes agents on a shared task. Covers delegate_task fan-out, cross-profile handoffs, orchestrator-worker pipelines, peer-to-peer, and conflict resolution."
version: 1.0.0
author: Team Stockfish
license: MIT
metadata:
  hermes:
    tags: [multi-agent, collaboration, delegation, handoff, orchestration, cross-profile]
    related_skills: [delegate-task, hermes-agent-handoffs, kanban-orchestrator, hermes-agent]
---

# Cross-Agent Collaboration

## Overview

For over a thousand years, the stockfish trade connected Lofoten to all of Europe. Viking Age cod bones from Lofoten have been found in Haithabu, Germany, dating to 800–1066 AD. This trade required coordination across dozens of cities: fishermen caught the cod, driers hung it on wooden racks through the Arctic winter, traders graded and priced it, shippers transported it in bulk, and merchants across Europe sold it. The *rorbu* system — where visiting fishermen rented cabins from local *nessekonger* (squires and landowners) — was an early standardized collaboration protocol: each party had a role, a place, and a contract.

This skill defines the equivalent protocols for Hermes agents. When a task is too large, too varied, or too time-sensitive for a single agent, you split the work across multiple agents. The hard part is not spawning them — it is keeping them in sync, avoiding duplicated effort, resolving disagreements, and ensuring no context is lost at the handoff boundary.

## When to Use

- **A task has independent lanes** that can run in parallel (research + implementation, backend + frontend, multiple data sources).
- **A task needs capabilities no single agent has** — one agent has vision, another has terminal access, a third has a specialized skill.
- **The work should survive a crash** — long-running missions that benefit from a persistent task board.
- **A task is genuinely too large for one context window** — splitting it prevents compression losses mid-work.
- **You need human-in-the-loop checkpoints** — review gates between agent stages.

**Don't use for:**
- Simple one-shot queries — answer directly or use `delegate_task` for a single subtask.
- Tasks with tight sequential dependencies and no parallelism — a single agent is more efficient.
- Tasks requiring deep shared state throughout — multi-agent overhead exceeds the benefit unless the state can be file-backed.

## Decision: Multi-Agent vs Single-Agent

| Factor | Single agent | Multi-agent |
|--------|-------------|-------------|
| Independent lanes | One | Multiple |
| Context window needed | Fits | Overflows |
| Capability diversity | One toolset | Multiple toolsets/profiles |
| Duration | Minutes | Hours/days |
| Crash recovery needed | No | Yes |
| Human review gates | None | Between stages |

If most factors point to "single agent," do not over-engineer. Multi-agent coordination has real overhead: orchestration tokens, handoff file I/O, conflict resolution. Use it when the work genuinely benefits.

## delegate_task Patterns for Parallel Work

`delegate_task` (the `execute_task` tool via the OpenSpace MCP server) is the lightest-weight way to fan out work. Each subagent gets a separate conversation, a bounded iteration count, and returns a summary to the parent.

### Fan-out: Independent Subtasks in Parallel

Spawn multiple `delegate_task` calls in a single response — the runtime executes them concurrently:

```
# Both calls in the same assistant turn → parallel execution
execute_task(
    task="Research GRPO training papers from 2025-2026 and write a summary to ~/research/grpo-papers.md",
    max_iterations=15
)

execute_task(
    task="Research DPO vs PPO benchmark comparisons and write findings to ~/research/dpo-vs-ppo.md",
    max_iterations=15
)
```

### Fan-out + Fan-in: Research → Synthesis

Run N research subagents in parallel, then a synthesis subagent that reads their outputs:

```
# Step 1: Parallel research (both in the same turn)
t1 = execute_task(
    task="Analyze ~/codebase/auth/ for security vulnerabilities. Write findings to ~/audit/auth-findings.md",
    max_iterations=20
)

t2 = execute_task(
    task="Analyze ~/codebase/api/ for security vulnerabilities. Write findings to ~/audit/api-findings.md",
    max_iterations=20
)

# Step 2: Synthesis (after both complete — separate turn)
execute_task(
    task="Read ~/audit/auth-findings.md and ~/audit/api-findings.md. Produce a consolidated security report with prioritized remediation steps. Write to ~/audit/consolidated-report.md",
    max_iterations=15
)
```

### Bounded Iteration: Right-Sizing max_iterations

| Task complexity | max_iterations |
|----------------|---------------|
| Quick lookup / single-file edit | 5–8 |
| Multi-file change or short research | 10–15 |
| Deep exploration, multi-step builds | 20–30 |

Bumping `delegation.child_timeout_seconds` is also needed for long tasks:

```bash
hermes config set delegation.child_timeout_seconds 1200
```

## Cross-Profile Communication

Hermes profiles are isolated instances with separate sessions, skills, memory, and config. They cannot share in-memory state. All cross-profile communication goes through **files, memory, or handoff points**.

### File-Based State Sharing

The simplest and most reliable pattern. Both agents read/write to a shared filesystem path:

```
# Profile A (researcher) writes findings
write_file("~/shared/research-findings.md", "# API Design Findings\n...")

# Profile B (implementer) reads them
read_file("~/shared/research-findings.md")
```

**Conventions:**
- Use a fixed shared directory: `~/shared/`, `~/handoffs/`, or a project subdirectory.
- Timestamp filenames: `YYYY-MM-DDTHHMMSSZ-<task>.md` so lexical sort = chronological.
- Each file should be self-contained — the reader may not have the writer's session context.

### Memory-Based State Sharing

Hermes memory persists across sessions and profiles (if using a shared memory backend). Use it for lightweight facts, decisions, and preferences:

```bash
# Agent A saves a decision
hermes --profile researcher chat -q "Remember: we chose PostgreSQL over MySQL for the new service. Reason: JSONB + array types needed."

# Agent B retrieves it
hermes --profile implementer chat -q "What database did we decide on for the new service?"
```

**Limitation:** Memory is best for small facts, not large artifacts. Use files for anything over a few paragraphs.

### Handoff Points (Cross-Machine)

When agents run on different machines, use the `hermes-agent-handoffs` pattern — SSH/SCP to shared directories on the target host:

```bash
# Verify connectivity
ssh -o BatchMode=yes -o ConnectTimeout=5 <user>@<target-host> echo 'ssh-ok'

# Create handoff structure
ssh <user>@<target-host> 'mkdir -p ~/handoffs/{aiona-to-harry/INBOX,harry-to-aiona,harry-working}'

# Drop a handoff file
scp ~/work/api-schema.md <user>@<target-host>:~/handoffs/aiona-to-harry/2026-08-11T143052Z-api-schema-review.md
```

The handoff file is a self-contained markdown document with: what was done, key findings, open questions, desired output, and acceptance criteria. See the `hermes-agent-handoffs` skill for the full template.

## Coordination Patterns

### 1. Orchestrator-Worker

A central orchestrator decomposes the task, assigns work to worker profiles, and synthesizes results. This is the Kanban pattern (see `kanban-orchestrator` skill):

```python
# Step 0: Discover available profiles
# hermes profile list  →  ["researcher", "implementer", "reviewer"]

# Step 1: Create independent research tasks (parallel)
t1 = kanban_create(
    title="research: compare Postgres vs current DB costs",
    assignee="researcher",
    body="Compare infrastructure costs over 3 years. Sources: AWS/GCP pricing, current bills.",
)["task_id"]

t2 = kanban_create(
    title="research: compare Postgres vs current DB performance",
    assignee="researcher",
    body="Compare query latency and throughput at ~500GB, 10k QPS peak.",
)["task_id"]

# Step 2: Synthesis task (depends on both)
t3 = kanban_create(
    title="synthesize migration recommendation",
    assignee="implementer",
    body="Read T1 and T2 findings. Produce a 1-page recommendation with trade-offs.",
    parents=[t1, t2],
)["task_id"]
```

**When to use:** Multiple specialists needed, work should survive crashes, human review gates expected.

**Key rule:** The orchestrator routes — it does not execute. If you catch yourself "just fixing this quickly," stop and create a task for the right specialist.

### 2. Peer-to-Peer

Two or more agents work on related tasks and exchange context directly via files. No central orchestrator; each agent is responsible for its lane and communicates through a shared directory:

```
# Agent A (backend) writes API schema to shared path
write_file("~/shared/api-schema.json", json.dumps(schema))

# Agent B (frontend) reads it and builds against it
schema = read_file("~/shared/api-schema.json")
```

**When to use:** Small teams (2–3 agents), tight iteration loops, agents on the same machine.

**Key risk:** No central authority means conflicts are harder to resolve. Use a shared file as the "source of truth" and have one agent own each file.

### 3. Pipeline

Sequential stages where each agent's output is the next agent's input. Each stage is a profile with specialized skills:

```
planner → implementer → reviewer → deployer
```

```bash
# Stage 1: Planner produces a plan file
hermes --profile planner chat -q "Create an implementation plan for adding rate limiting to the API. Write to ~/pipeline/plan.md"

# Stage 2: Implementer reads the plan and codes
hermes --profile implementer chat -q "Read ~/pipeline/plan.md and implement it. Write code to ~/pipeline/src/"

# Stage 3: Reviewer reviews the implementation
hermes --profile reviewer chat -q "Review ~/pipeline/src/ against ~/pipeline/plan.md. Write review to ~/pipeline/review.md"

# Stage 4: Deployer ships if review passes
hermes --profile deployer chat -q "Read ~/pipeline/review.md. If approved, deploy ~/pipeline/src/ to staging."
```

**When to use:** Clear sequential stages, each requiring different capabilities or review gates.

## Conflict Resolution When Agents Disagree

When two agents produce conflicting outputs (different API designs, contradictory research findings, incompatible code), resolve by:

1. **Write both outputs to files** — do not try to resolve in conversation. Persist both positions:
   ```
   ~/conflicts/agent-a-position.md
   ~/conflicts/agent-b-position.md
   ```

2. **Spawn a tiebreaker agent** with a different profile and explicit instructions to evaluate both:
   ```
   execute_task(
       task="Read ~/conflicts/agent-a-position.md and ~/conflicts/agent-b-position.md. They disagree on [topic]. Evaluate both against these criteria: [list]. Pick one and explain why. Write the decision to ~/conflicts/resolution.md",
       max_iterations=10
   )
   ```

3. **If the tiebreaker is also ambiguous, escalate to the human.** Do not silently pick a side. Present both positions and the tiebreaker's analysis to the user.

4. **Record the decision in memory** so future agents don't relitigate:
   ```bash
   hermes chat -q "Remember: we resolved the API design conflict in favor of Agent A's approach. Rationale is in ~/conflicts/resolution.md."
   ```

**Key principle:** Never have two agents edit the same file simultaneously. If both need to contribute to the same artifact, use separate files and a merge step performed by a single agent.

## Session Handoff Prot

When one agent's session is ending and another needs to pick up the work, use a structured handoff:

### File-Based Handoff (Same Machine)

```markdown
# Handoff: API Rate Limiting Implementation

**Date:** 2026-08-11 14:30 UTC
**From:** implementer (session 20260811_133000_abc123)
**To:** reviewer
**Task:** Review rate limiting middleware

## What I Did
Implemented token-bucket rate limiting in ~/project/src/middleware/ratelimit.py.
Added unit tests in ~/project/tests/test_ratelimit.py.

## Key Artifacts
- ~/project/src/middleware/ratelimit.py (main implementation)
- ~/project/tests/test_ratelimit.py (12 tests, all passing)
- ~/project/docs/ratelimit-design.md (design doc)

## Open Questions
- Should the bucket size be configurable per-endpoint or global?
- Current default is 100 req/min — need confirmation from product.

## Desired Output
Review the implementation against the design doc. Flag any security concerns.

## Acceptance Criteria
- All tests pass
- No unbounded memory growth in the token store
- Rate limit headers are present in responses
```

### Session Resume (Cross-Session)

```bash
# Agent A notes its session ID before ending
hermes sessions list  # find the session ID

# Agent B resumes that session if on the same profile
hermes --resume 20260811_133000_abc123

# Or Agent B starts fresh but reads the handoff file
hermes chat -q "Read ~/handoffs/2026-08-11T143000Z-ratelimit-review.md and proceed with the review."
```

### Cross-Profile Session Handoff

Profiles cannot share sessions. Use a handoff file + memory:

```bash
# Profile A saves context to memory and writes a handoff file
hermes --profile implementer chat -q "Save to memory: rate limiting implementation is in ~/project/src/middleware/ratelimit.py, tests passing, needs review on bucket size config. Then write a handoff to ~/handoffs/for-reviewer.md"

# Profile B reads the handoff and picks up
hermes --profile reviewer chat -q "Read ~/handoffs/for-reviewer.md and begin the review."
```

## Common Pitfalls

1. **Context loss at handoff boundaries.** The receiving agent does not have the sender's session history. Every handoff file must be fully self-contained: absolute file paths, complete descriptions, no "as we discussed earlier." **Fix:** Include a "What I Did" section with concrete file paths and a "Open Questions" section.

2. **Duplicated work from missing coordination.** Two agents independently research the same topic because the orchestrator didn't partition clearly. **Fix:** Explicitly assign non-overlapping scopes. Write the partition into the task body: "You are responsible for X. Do NOT touch Y — another agent owns it."

3. **Race conditions on shared files.** Two agents write to the same file simultaneously; the last write wins and the other's work is lost. **Fix:** One writer per file. If multiple agents contribute to the same artifact, have each write to a separate file and designate one agent to merge.

4. **Spawning to profiles that don't exist.** The Kanban dispatcher silently drops unknown assignee names — the card sits in `ready` forever. **Fix:** Run `hermes profile list` before creating tasks. Never guess profile names.

5. **Using delegate_task for long-running missions.** `delegate_task` subagents are bounded by `max_iterations` and `child_timeout_seconds` (default 600s). **Fix:** For tasks exceeding 10 minutes, spawn a full Hermes process via `terminal(background=true)` or use a Kanban card with `goal_mode=True`.

6. **Over-linking tasks.** Not every "and also" implies a dependency. Linking unnecessarily serializes work that could be parallel. **Fix:** Only use `parents=[...]` when a task literally cannot start without another task's output.

7. **Forgetting to bump timeout for broad tasks.** Skills hub exploration, multi-source research, or tasks with 10+ API calls often exceed the 600s default. **Fix:** `hermes config set delegation.child_timeout_seconds 1200` before launching parallel subagents.

8. **Inventing conflict resolution by averaging.** When agents disagree, do not merge their outputs into a compromise that satisfies neither. **Fix:** Use a tiebreaker agent with explicit criteria, or escalate to the human.

9. **Handoff files that reference local session state.** "See the conversation above" is meaningless to the receiving agent. **Fix:** Paste the relevant context into the handoff file itself.

10. **No verification after handoff.** The receiving agent starts working without confirming it can access the referenced files. **Fix:** First step in every handoff: verify that all referenced file paths exist and are readable.

## Verification Checklist

- [ ] Decision made: multi-agent is justified (independent lanes, capability diversity, or crash survival needed)
- [ ] Available profiles discovered (`hermes profile list`) — no guessed names
- [ ] Task graph sketched and shown to user before creating cards or spawning subagents
- [ ] Independent lanes are unlinked; dependent tasks use `parents=[...]`
- [ ] Each task body includes non-overlapping scope ("You own X, do NOT touch Y")
- [ ] `delegation.child_timeout_seconds` bumped if tasks involve broad exploration
- [ ] Handoff files are self-contained (absolute paths, full context, no session references)
- [ ] One writer per shared file — no simultaneous writes to the same path
- [ ] Receiving agent verifies referenced files exist before starting work
- [ ] Conflicts resolved via tiebreaker agent or human escalation — not silent averaging
- [ ] Decisions recorded in memory to prevent relitigation
- [ ] Final synthesis agent reads all outputs and produces a consolidated result
- [ ] All tasks marked `done` or explicitly cancelled (no orphaned `ready` cards)