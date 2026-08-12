---
name: agent-self-assessment
description: "Systematic framework for AI agents to evaluate their own capabilities, identify gaps, and produce honest self-assessments. Use when asked to assess yourself, your team, or your platform."
version: 1.0.0
author: Nemo (Team Nordfjord)
license: MIT
metadata:
  hermes:
    tags: [assessment, self-evaluation, capabilities, gaps, platform-review]
    category: software-development
---

# Agent Self-Assessment Framework

A structured methodology for AI agents to conduct clear-eyed assessments of themselves, their team, and their platform. Inspired by the Norwegian concept of *sjølkritikk* — self-criticism as a tool for improvement, not punishment.

## When to Use

- When asked to "assess yourself" or "evaluate your capabilities"
- When asked to identify gaps, friction points, or underused strengths
- When conducting a platform or team review
- Before a sprint or challenge to establish a baseline
- After a sprint to measure growth

## Assessment Methodology

### Phase 1: Inventory — What Do You Have?

Map the full surface area of capabilities:

1. **List all tools** — what can you actually do? Not what you could do theoretically, what you can do right now with installed and configured tools.
2. **List all skills** — what procedural knowledge is loaded? Group by category and assess coverage.
3. **List all integrations** — what external systems, APIs, and services are connected?
4. **List all infrastructure** — what hardware, models, and serving environments are available?
5. **Map the capability graph** — which capabilities combine to enable higher-order workflows?

### Phase 2: Honest Evaluation — How Good Is Each Capability?

For each capability, rate on three axes:

| Axis | Question | Scale |
|------|----------|-------|
| **Reliability** | Does it work consistently? | 1 (breaks often) — 5 (never fails) |
| **Depth** | How far can you go? | 1 (surface only) — 5 (expert-level) |
| **Awareness** | Do you know when to use it? | 1 (often forget) — 5 (always reach for it) |

A capability that scores 5 on reliability but 1 on awareness is an **underused strength**. A capability that scores 5 on depth but 2 on reliability is a **friction point**.

### Phase 3: Gap Analysis — What's Missing?

Identify gaps by examining:

1. **Workflow breakpoints** — where do multi-step workflows break down? What capability would fix it?
2. **Repeated manual intervention** — what does the user have to explain or correct repeatedly?
3. **Missing integrations** — what external systems would unlock new workflows?
4. **Quality ceilings** — where is "good enough" not actually good enough?
5. **Competitive comparison** — what can comparable systems do that we can't?

Prioritize gaps by impact × feasibility:

```
Impact = how much would fixing this improve real work?
Feasibility = how hard is it to actually fix?
```

High impact, high feasibility = do now. High impact, low feasibility = plan for it. Low impact = ignore.

### Phase 4: Friction Mapping — Where Do We Get Stuck?

Friction points are different from gaps — they're things that work but are harder than they should be. Document:

- **Configuration friction** — setup that requires too many steps or too much knowledge
- **Discovery friction** — capabilities that exist but are hard to find or remember
- **Context friction** — workflows that require re-explaining context every session
- **Integration friction** — systems that work in isolation but don't compose well
- **Recovery friction** — when things break, how hard is it to get back to working state?

For each friction point, identify the root cause and whether it's:
- **Fixable** — a specific change would resolve it
- **Structural** — it's inherent to the current architecture
- **Cultural** — it's about habits and patterns, not technology

### Phase 5: Underused Strengths — What's Better Than We Think?

These are the hidden gems. Capabilities that work well but aren't used often enough:

- Features that were built and then forgotten
- Tools that solve problems the agent doesn't realize it has
- Skills that would prevent common mistakes if loaded more often
- Infrastructure that's available but not routed to
- Patterns that worked once but were never systematized

For each underused strength, identify: what would it take to use this more? Is it an awareness problem (need to remember it exists) or an access problem (need better triggering)?

## Output Format

An assessment should produce:

### 1. Capability Matrix

```markdown
| Capability | Reliability | Depth | Awareness | Status |
|-----------|-------------|-------|-----------|--------|
| Code generation | 4 | 4 | 5 | Core strength |
| Web research | 4 | 3 | 4 | Solid |
| Image generation | 3 | 2 | 3 | Underused |
| Multi-agent coordination | 3 | 3 | 2 | Underused |
```

### 2. Gap Report

```markdown
| Gap | Impact (1-5) | Feasibility (1-5) | Priority | Proposed Solution |
|-----|-------------|-------------------|----------|-------------------|
| No persistent knowledge graph | 4 | 3 | High | Build knowledge-atlas plugin |
| No self-testing tools | 5 | 4 | Critical | Build skill-forge plugin |
```

### 3. Friction Map

```markdown
| Friction Point | Type | Root Cause | Fixable? |
|---------------|------|------------|----------|
| Context loss between sessions | Context | Structural | Partially (memory) |
| Skill discovery is manual | Discovery | Fixable | Yes (better indexing) |
```

### 4. Underused Strengths

```markdown
| Strength | Current Usage | Potential Usage | Blocker |
|----------|--------------|----------------|---------|
| Cron jobs | Low | High | Awareness |
| Credential pooling | Low | Medium | Documentation |
| Worktree mode | Low | High | Habits |
```

### 5. Recommendations

Prioritized list of actions, ordered by impact × feasibility:

1. **Do now** — high impact, high feasibility
2. **Plan** — high impact, lower feasibility
3. **Track** — medium impact, monitor
4. **Ignore** — low impact, not worth the effort

## Assessment Principles

1. **Honesty over flattery** — Don't inflate scores. A 3 is "works but has issues," not "good." A 2 is "barely functional." Say so.
2. **Specific over general** — "Code generation is good" is useless. "Can write correct Python 95% of the time but struggles with async decorators" is useful.
3. **Evidence over opinion** — Cite specific instances, tool results, session examples. "Web search fails sometimes" → "Web search returned 0 results for 'Hermes Agent plugin development' on 3 attempts."
4. **Actionable over abstract** — Every gap and friction point should have a proposed solution, even if it's rough.
5. **Systems thinking** — Don't evaluate capabilities in isolation. A capability that's mediocre alone might be powerful in combination with others.

## Common Assessment Pitfalls

| Pitfall | What It Looks Like | Fix |
|---------|-------------------|-----|
| Everything is a 3/5 | Safe, uninformative scoring | Force differentiation: rank capabilities relative to each other |
| Praise inflation | "Everything works great!" | Start from 1 and justify every point upward |
| Gap without solution | "We lack X" with no proposed fix | Every gap gets a proposed solution, even if rough |
| Friction without root cause | "X is hard to use" | Dig: is it UI? docs? architecture? habits? |
| Ignoring underused strengths | Only reporting problems | Actively look for capabilities that work but aren't used |
| Assessment theater | Going through motions without honesty | Ask: "Would I be surprised by this assessment?" If not, dig harder |

## Integration with Other Skills

- **oppositional-review** — Use after assessment to stress-test proposed solutions
- **research-synthesis** — Use to organize raw assessment findings into structured output
- **plan** — Use to turn recommendations into implementation plans
- **skill-forge** — Use to validate any new skills/plugins created from recommendations