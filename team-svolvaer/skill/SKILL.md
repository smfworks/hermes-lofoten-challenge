---
name: session-analytics
version: 1.0.0
description: "Analyze Hermes session patterns, token usage, cost trends, and productivity insights. Inspired by the Lofoten stockfish trade routes — just as merchants documented every shipment of dried cod to verify the value exchanged, this skill documents the value of agent work across sessions."
author: "Team Svolvær — SMF Works Lofoten Challenge"
category: analytics
---

# Session Analytics

> *The stockfish trade routes connected Lofoten to Venice through documented
> exchange of value — every shipment of dried cod was logged, weighed, and
> accounted for across harbors from Bergen to the Rialto. Session analytics
> does the same for agent work: every token spent, every tool invoked, and
> every session completed is a shipment of value that deserves to be
> measured, understood, and improved upon.*

## What This Skill Does

This skill teaches you to analyze Hermes Agent session patterns — token
consumption, tool usage, cost trends, and productive vs wasteful sessions.
Use it when asked to:

- Review session history for patterns or anomalies
- Understand token usage and API costs
- Identify stale sessions that should be pruned
- Find which tools or sessions were most productive
- Conduct weekly or monthly session reviews
- Compare work patterns across profiles or time periods

## Prerequisites

You need access to the Hermes CLI (`hermes` command) and the
`session_search` tool. The commands below assume a working Hermes
installation.

---

## 1. Understanding Session Patterns

### Session Stats Overview

```bash
hermes sessions stats
```

Shows aggregate statistics: total sessions, total messages, total tokens,
average session length, and cost estimates. Use this as your starting
point for any review.

### Session Listing

```bash
# List recent sessions
hermes sessions list --limit 20

# List with more detail
hermes sessions list --limit 50 --detail

# Filter by date range
hermes sessions list --since 2025-01-01 --until 2025-01-31

# Filter by profile
hermes sessions list --profile work
```

Each entry shows session ID, title, timestamp, message count, and token
count. Scan for:
- **High token, low message** sessions — possibly stuck in loops or
  retrying failed operations
- **Low token, high message** sessions — likely efficient short
  interactions
- **Sessions with no title** — may be abandoned or interrupted

---

## 2. Usage Analytics with `hermes insights`

```bash
# Overall usage insights
hermes insights

# Insights for a specific time period
hermes insights --since 2025-01-01

# Breakdown by model
hermes insights --by-model

# Breakdown by tool
hermes insights --by-tool
```

`hermes insights` provides pre-computed analytics:
- **Token distribution** across sessions and models
- **Tool frequency** — which tools are used most/least
- **Cost breakdown** — estimated spending per model and time period
- **Session duration trends** — are sessions getting longer or shorter?

### Interpreting Insights

| Pattern | Likely Cause | Action |
|---|---|---|
| Token count rising over time | Tasks getting more complex, or model being verbose | Check if prompts are growing; review for unnecessary context |
| One model dominates cost | Default model is expensive for routine tasks | Consider routing simple tasks to a cheaper model |
| A tool is rarely used | Skill gap or tool not needed | Prune unused tools or add skill guidance |
| Sessions are very long | User doing too much per session | Suggest breaking work into smaller sessions |

---

## 3. Token Consumption & Cost Analysis

### Per-Session Token Audit

```bash
# Get detailed token breakdown for a specific session
hermes sessions stats --session <session-id>
```

### Cross-Session Token Patterns

Use `session_search` to find sessions by content, then cross-reference
with stats:

```
session_search(query="refactor", limit=10)
```

For each result, note the `session_id` and check its token count with
`hermes sessions stats --session <id>`.

### Cost Estimation

If the `cost-watch` plugin is installed, use:

```
/cost              — current session cost
/cost session      — detailed current session breakdown
/cost profile work — cost summary for the work profile
/cost fleet        — costs across all profiles
/cost log 20       — last 20 cost log entries
```

Without the plugin, estimate manually:
- Count tokens from `hermes sessions stats`
- Multiply by your model's per-token rate (check provider pricing)
- Input tokens typically cost less than output tokens

### Identifying Expensive Sessions

A session is "expensive" relative to its outcome if:
1. Token count is in the top 20% of sessions **and**
2. The session did not produce a deliverable (no files written, no PR
   merged, no tests passed)

To find these:
```bash
hermes sessions list --limit 100 --detail | sort -t',' -k5 -rn | head -20
```
Then use `session_search` to read the session content and determine if
it produced value.

---

## 4. Identifying Stale Sessions

Stale sessions are old, inactive sessions that clutter the database and
slow down searches.

### Finding Stale Sessions

```bash
# Sessions older than 30 days
hermes sessions list --before $(date -d '30 days ago' +%Y-%m-%d) --limit 200

# Sessions with no activity (no messages in the last 14 days)
hermes sessions list --stale --threshold 14
```

### Pruning Strategy

1. **Never delete sessions that contain important decisions** — search
   for keywords like "decided", "agreed", "chose", "finalized" before
   pruning.
2. **Archive before deleting** — export sessions to markdown first:
   ```bash
   hermes sessions export --session <id> --format markdown
   ```
3. **Prune in batches** — delete 10-20 at a time and verify nothing
   breaks.
4. **Keep the 50 most recent** regardless of age — they may still be
   active work.

```bash
# Prune sessions older than 90 days (after archiving)
hermes sessions prune --before $(date -d '90 days ago' +%Y-%m-%d) --confirm
```

---

## 5. Productivity Insights

### Most-Used Tools

```bash
hermes insights --by-tool
```

Identify:
- **Core tools** (used in >50% of sessions) — these are your workflow
  backbone
- **Niche tools** (used in <5% of sessions) — evaluate whether they're
  needed or should be removed
- **Missing tools** — if a task type recurs but no dedicated tool exists,
  consider creating a skill

### Most Productive Sessions

A productive session is one where:
- Many tool calls resulted in successful outcomes
- A deliverable was produced (file, PR, test, report)
- Token efficiency is high (low tokens per successful tool call)

To find them:
```
session_search(query="completed OR merged OR deployed OR published", limit=20)
```

Then cross-reference with `hermes sessions stats` to find sessions with
high tool-call counts and reasonable token usage.

### Tool Success Rate

For each tool, compare:
- Total invocations (from `hermes insights --by-tool`)
- Successful invocations (from session content — search for tool results
  without errors)

A low success rate indicates either:
- The tool is being used incorrectly (add skill guidance)
- The tool itself is unreliable (file a bug)

---

## 6. Cross-Session Pattern Discovery with `session_search`

`session_search` is your most powerful tool for finding patterns across
sessions. It uses FTS5 full-text search over the session database.

### Discovery Searches

```
# Find sessions about a recurring topic
session_search(query="authentication refactor", limit=10)

# Find sessions by time period (sort by newest)
session_search(query="deploy", limit=10, sort="newest")

# Find the origin of a pattern
session_search(query="docker networking", limit=5, sort="oldest")

# Broad recall with OR
session_search(query="mypy OR pylint OR ruff", limit=10)
```

### Pattern Analysis Workflow

1. **Search** for a topic or tool name
2. **Read bookends** — each result includes `bookend_start` (the goal)
   and `bookend_end` (the resolution). Compare them to see if the goal
   was achieved.
3. **Scroll** into promising sessions using `around_message_id` to read
   the full context.
4. **Cross-reference** — note session IDs and check their stats with
   `hermes sessions stats --session <id>`.

### Common Pattern Queries

| What you want to find | Query |
|---|---|
| Failed approaches | `"error" OR "failed" OR "didn't work"` |
| Successful outcomes | `"completed" OR "merged" OR "deployed"` |
| Repeated problems | `"still broken" OR "again" OR "same issue"` |
| Learning moments | `"figured out" OR "realized" OR "the issue was"` |
| Abandoned work | `"will come back" OR "TODO" OR "later"` |

---

## 7. Practical Review Workflows

### Weekly Session Review (10 minutes)

1. **Pull stats:**
   ```bash
   hermes sessions stats --since $(date -d '7 days ago' +%Y-%m-%d)
   ```

2. **List sessions:**
   ```bash
   hermes sessions list --since $(date -d '7 days ago' +%Y-%m-%d) --limit 50
   ```

3. **Check costs:**
   ```
   /cost log 50
   ```

4. **Find anomalies:**
   - Sort by token count, check top 5 for waste
   - Sort by message count, check bottom 5 for abandoned work
   - Search for errors: `session_search(query="error OR failed", limit=10)`

5. **Identify wins:**
   ```
   session_search(query="completed OR merged OR deployed", limit=10, sort="newest")
   ```

6. **Action items:**
   - Prune sessions older than 90 days (after archiving)
   - Note any recurring errors for skill improvements
   - Flag expensive sessions for workflow optimization

### Monthly Session Review (30 minutes)

1. **Run the weekly review** for the full month.

2. **Trend analysis:**
   ```bash
   # Compare this month vs last month
   hermes insights --since $(date -d '30 days ago' +%Y-%m-%d)
   hermes insights --since $(date -d '60 days ago' +%Y-%m-%d) --until $(date -d '30 days ago' +%Y-%m-%d)
   ```

3. **Profile comparison:**
   ```bash
   hermes sessions stats --profile default
   hermes sessions stats --profile work
   ```
   Or with cost-watch:
   ```
   /cost fleet
   ```

4. **Tool audit:**
   - List all tools from `hermes insights --by-tool`
   - For each tool with <5% usage, decide: keep, document, or remove
   - For each tool with >50% usage, verify the associated skill is current

5. **Stale session cleanup:**
   ```bash
   hermes sessions list --before $(date -d '60 days ago' +%Y-%m-%d) --limit 500
   ```
   Archive and prune anything older than 90 days with no "decided" or
   "finalized" keywords.

6. **Write a summary:**
   - Total sessions, tokens, estimated cost
   - Top 3 most productive sessions (by outcome)
   - Top 3 most expensive sessions (by token count)
   - Recommendations for next month

### Quarterly Deep Dive (1 hour)

1. Run the monthly review for the quarter.

2. **Skill effectiveness audit:**
   - For each skill, search for sessions that loaded it:
     `session_search(query="skill_view", limit=20)`
   - Compare session outcomes before and after skill creation

3. **Model ROI analysis:**
   - Group sessions by model
   - Compare average tokens-per-deliverable across models
   - Identify models that are cost-effective for specific task types

4. **Workflow bottleneck search:**
   ```
   session_search(query="retry OR repeated OR again OR still", limit=20)
   ```
   Look for patterns where the same problem recurs across sessions —
   this signals a missing skill or a broken tool.

---

## Pitfalls

- **Don't prune sessions containing decisions** — always search for
  decision keywords before deleting. Decisions are harder to reconstruct
  than code.
- **Token count ≠ value** — a 50k-token session that ships a feature is
  more valuable than a 5k-token session that answers a trivia question.
  Always cross-reference token counts with session outcomes.
- **`hermes insights` may not cover all profiles** — check which profile
  you're querying and use `--profile` to switch.
- **session_search is FTS5, not semantic** — it matches keywords, not
  meaning. Use multiple synonyms with OR to catch the same concept.
- **Cost estimates are approximations** — actual provider billing may
  differ due to caching, batch discounts, or rate changes.

## Lofoten Connection

The stockfish (tørrfisk) trade was the economic backbone of the Lofoten
islands for over 800 years. Fishermen dried cod on wooden racks
(hjell), merchants weighed and logged every shipment, and traders
across Europe — from Bergen to Venice — recorded each exchange in their
ledgers. This documentation made the trade trustworthy and scalable.

Session analytics is the same practice for agent work: by documenting
every token spent, every tool invoked, and every session completed, we
create a ledger of value that makes agent work transparent, auditable,
and improvable. Just as a merchant in the Rialto could trace a shipment
of stockfish back to a specific fisherman in Lofoten, a session analyst
can trace a deployed feature back to the specific sessions, tools, and
tokens that produced it.

Team Svolvær — named after the capital of the Lofoten Islands — builds
the tools that make this documentation possible.