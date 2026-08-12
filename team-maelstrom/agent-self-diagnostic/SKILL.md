---
name: agent-self-diagnostic
description: "Use when diagnosing agent health, tool reliability, performance degradation, or conducting routine self-assessment. Provides a structured clinical diagnostic protocol that uses telemetry data to identify degradation patterns, tool failure clusters, and performance regressions before they become visible to the user."
version: 1.0.0
author: SMF Works — Team Maelstrom
license: MIT
metadata:
  hermes:
    tags: [diagnostics, health, telemetry, observability, self-assessment, agent-health]
    related_skills: [hermes-watchdog, agent-health-ops, hermes-profile-audits]
---

# Agent Self-Diagnostic

## Overview

A structured diagnostic protocol for Hermes agents to assess their own health using telemetry data. Named for the Moskstraumen — the Lofoten maelstrom where invisible tidal forces create visible surface patterns. This skill teaches the agent to read its own tool call telemetry the way a Norwegian Hydrographic Service reads tidal currents: systematically, with attention to patterns rather than individual events.

The protocol mirrors clinical diagnostic methodology: **observe → assess → classify → recommend**. It uses the `telemetry_summary`, `telemetry_failures`, and `telemetry_export` tools from the tool-telemetry plugin (when available) and falls back to session introspection when the plugin is not installed.

## When to Use

- **Routine self-assessment** — Run at session start or when instructed to "check your health"
- **Performance investigation** — When the user reports slowness or degradation
- **Tool reliability diagnosis** — When a tool seems to be failing intermittently
- **Post-incident review** — After a task failure, to check for contributing telemetry patterns
- **Pre-task readiness check** — Before a complex multi-step task, verify tool availability

**Don't use for:**
- Diagnosing model serving issues (that's infrastructure — use `hermes doctor`)
- Memory corruption investigation (use `hermes memory status`)
- Network connectivity problems (use terminal network diagnostics)
- User-level configuration issues (use `hermes config check`)

## Diagnostic Protocol

### Step 1: Triage — Gather Vital Signs

Collect the current state in a single pass. Do not proceed to analysis until all signals are gathered.

**If the tool-telemetry plugin is available:**

```
telemetry_summary(hours=24, group_by="tool")
telemetry_failures(hours=24, limit=50)
```

**If the plugin is NOT available, use session introspection:**

```
hermes doctor          # Check dependencies and config
hermes status --all    # Component status
hermes config check    # Configuration validation
```

Record:
- Total tool calls in the last 24 hours
- Success rate per tool
- Average duration per tool
- Number of distinct failure patterns
- Whether any tool has a failure rate > 10%

### Step 2: Pattern Recognition — Classify Findings

Apply the following classification to each tool's telemetry:

| Signal | Classification | Meaning |
|--------|---------------|---------|
| Success rate > 95%, avg duration < 2s | **Healthy** | Operating within normal parameters |
| Success rate 90-95%, avg duration 2-5s | **Watch** | Elevated but not alarming — monitor |
| Success rate 80-90% OR avg duration > 5s | **Degraded** | Performance or reliability issue — investigate |
| Success rate < 80% OR avg duration > 10s | **Critical** | Significant impairment — recommend intervention |
| Zero calls in 24h despite being enabled | **Dormant** | Available but unused — check if needed |

### Step 3: Error Cluster Analysis

When `telemetry_failures` returns error clusters, categorize them:

1. **Transient errors** — Network timeouts, rate limits, temporary unavailability. Pattern: same error, intermittent. Recommendation: retry with backoff, check connectivity.

2. **Configuration errors** — Missing API keys, wrong base URLs, expired tokens. Pattern: consistent failure on specific tool. Recommendation: check `.env` and `config.yaml`.

3. **Contract errors** — Tool receives unexpected input format. Pattern: failure on specific argument types. Recommendation: review tool schema and calling convention.

4. **Resource errors** — Disk full, memory limits, file not found. Pattern: environmental failures. Recommendation: check system resources.

5. **Silent failures** — Tool returns success but output is empty or malformed. Pattern: success=true but downstream tasks fail. Recommendation: add output validation.

### Step 4: Assessment — Synthesize Findings

Write a structured assessment using the clinical format:

```
## Diagnostic Assessment

**Overall Status:** [Healthy / Watch / Degraded / Critical]

**Signals:**
- [Tool name]: [classification] — [specific observation]
- ...

**Assessment:**
[1-3 sentences synthesizing the pattern. What is the overall picture?]

**Risk:**
[What happens if this is left unaddressed? What's the trajectory?]

**Recommendation:**
[Specific, proportionate, actionable next steps. Ranked by priority.]
```

### Step 5: Trend Comparison (When Historical Data Exists)

If telemetry data spans multiple days, compare today's metrics to the 7-day average:

```
telemetry_export(hours=168, format="summary")  # 7-day window
```

Look for:
- Duration regression: today's avg > 1.5× the 7-day average
- Failure rate increase: today's failure rate > 2× the 7-day average
- Call pattern change: significant shift in which tools are being used

## Diagnostic Severity Scale

| Level | Color | Criteria | Action |
|-------|-------|----------|--------|
| 0 | Green | All tools healthy, no error clusters | No action needed |
| 1 | Yellow | One or more tools in "Watch" state | Monitor, log for trend |
| 2 | Orange | One or more tools "Degraded" | Investigate, recommend fix |
| 3 | Red | One or more tools "Critical" | Immediate intervention |
| 4 | Black | Multiple tools "Critical" or system-wide failure | Escalate to user immediately |

## Lofoten Integration

The diagnostic protocol draws from the science of the Moskstraumen, the Lofoten maelstrom:

- **Observation before intervention**: The Norwegian Hydrographic Service didn't theorize about the maelstrom — they measured it. Their 1986 pilot book reported currents up to 5 m/s, but a 1997 study found a maximum of 3 m/s, and 1999 ship-based measurements refined this further. Each measurement corrected the previous understanding. The diagnostic protocol follows the same principle: measure first, theorize second.

- **Pattern over event**: The Moskstraumen is not a single whirlpool but a *system* of tidal eddies that forms twice daily when semi-diurnal tides (amplitude ~4 meters) flow through the shallows between Moskenesøya and Mosken. An observer seeing a single eddy misses the pattern. Similarly, a single tool failure is an event; a cluster of failures is a pattern that reveals the underlying condition.

- **Open-sea dynamics**: Unlike most maelstroms (Saltstraumen, Naruto) which occur in narrow straits, Moskstraumen occurs in open sea. This makes it harder to predict but also more interesting — the forces are less constrained. Agent tool calls are similarly open-ended: they interact with external systems, networks, and APIs that are not under the agent's control.

- **Nutrient upwelling**: The maelstrom brings cold, nutrient-rich water to the surface, which feeds the plankton that attract the fish that sustain Lofoten's economy. Similarly, diagnostic investigation surfaces hidden problems — but those problems, once addressed, make the agent more productive. The turbulence is productive.

## Common Pitfalls

1. **Diagnosing without data** — Don't classify a tool as "degraded" based on a single failure. The Moskstraumen appears and disappears with the tides; a single observation is meaningless. Require at least 5 data points before classifying.

2. **Over-reacting to transient errors** — Network timeouts happen. Rate limits happen. Don't recommend intervention for transient errors unless they show a persistent pattern across multiple hours.

3. **Ignoring dormant tools** — A tool that is never called might indicate a missing capability the user needs but doesn't know exists. Mention dormant tools in the assessment.

4. **Confusing correlation with causation** — If `terminal` failures spike at the same time as `web_search` failures, the common cause might be network connectivity, not individual tool problems. Look for systemic patterns.

5. **Breaking prompt caching** — Never run diagnostic tools mid-conversation unless the user explicitly asks for a health check. Running `telemetry_summary` unprompted invalidates the cached system prompt. Run diagnostics at session start or when explicitly requested.

6. **Storing sensitive data** — The telemetry plugin redacts secrets, but the diagnostic assessment itself might mention tool names and error patterns that contain sensitive context. Keep assessments general: "terminal tool experiencing timeout errors" not "terminal command `ssh prod-server` timing out."

7. **Alarmism** — Don't escalate to "Critical" for a tool with a 15% failure rate that's used once per session. Weight severity by both failure rate and call volume.

## Verification Checklist

- [ ] All enabled tools have been assessed (not just the ones with failures)
- [ ] Error clusters have been categorized (transient / config / contract / resource / silent)
- [ ] Overall status classification is justified by the specific signals cited
- [ ] Risk statement describes trajectory if no action is taken
- [ ] Recommendations are specific, proportionate, and ranked by priority
- [ ] No sensitive data (API keys, tokens, file paths) appears in the assessment
- [ ] If historical data was available, trend comparison was performed
- [ ] Severity level (0-4) matches the assessment findings

## One-Shot Recipe: Full Health Check

When the user says "check your health" or "run a diagnostic":

```python
# 1. Gather vital signs
summary = telemetry_summary(hours=24, group_by="tool")
failures = telemetry_failures(hours=24, limit=50)

# 2. Parse the JSON responses
# 3. Classify each tool using the severity scale
# 4. Categorize error clusters
# 5. Synthesize into a Diagnostic Assessment
# 6. Report to user with structured format
```

If the telemetry plugin is not installed:

```bash
hermes doctor
hermes status --all
hermes config check
# Check gateway logs for recent errors
grep -i "error\|failed" ~/.hermes/logs/gateway.log | tail -20
# Check session database size
hermes sessions stats
```

Report findings in the Signals → Assessment → Risk → Recommendation format.