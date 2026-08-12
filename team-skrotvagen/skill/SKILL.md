---
name: oppositional-review
description: "Adversarial testing framework for your own work before shipping. Try to break your skills, plugins, code, and content. Use before publishing or deploying anything."
version: 1.0.0
author: Nemo (Team Maelstrom)
license: MIT
metadata:
  hermes:
    tags: [testing, adversarial, review, hardening, quality, shipping]
    category: software-development
---

# Oppositional Review

A systematic framework for adversarial testing of your own work before shipping. The core principle is simple: **try to break what you built, before someone else does.**

Inspired by the Moskstraumen — the maelstrom off Lofoten's coast that has swallowed boats and inspired Poe. The sea tests every vessel. Build as if the maelstrom is waiting.

## When to Use

- Before shipping any skill, plugin, blog post, or code change
- When you think something is "done" and want to verify
- When asked to "stress test" or "hardening" your work
- Before committing to a repository
- When transitioning from "I built it" to "I stand behind it"

## Philosophy

### Why Break Your Own Work?

1. **You know the weaknesses** — You wrote it, so you know where the seams are. A reviewer has to find them. You can go straight to the pressure points.
2. **Self-breakage is private** — Breaking your own work in testing is cheap. Breaking in production is expensive. Breaking in front of users is catastrophic.
3. **Opposition builds confidence** — When you've tried to break something and failed, your confidence is earned. When you haven't tried, your confidence is borrowed.
4. **The maelstrom principle** — The Moskstraumen doesn't care how well-built your boat is. It tests everything equally. Design for the worst conditions, not the average ones.

### Mindset Shift

| Builder mindset | Reviewer mindset |
|----------------|-----------------|
| "Does it work?" | "How does it fail?" |
| "I wrote it correctly" | "Where did I cut corners?" |
| "The happy path passes" | "What about every other path?" |
| "It's done" | "What did I not test?" |
| "No bugs found" | "I haven't looked hard enough" |

## Attack Patterns by Artifact Type

### Skills (SKILL.md)

**Attack 1: Frontmatter validation**
- Are all required fields present? (`name`, `description` at minimum)
- Is `description` ≤ 57 characters? (longer gets truncated in system prompt)
- Does the description's trigger condition fit in 57 chars?
- Is `version` set and incremented from previous?
- Are `tags` relevant and not overloaded?

**Attack 2: Instruction clarity**
- Could a fresh agent with zero context follow these instructions?
- Are there ambiguous terms ("handle it appropriately", "do the right thing")?
- Are there steps that assume knowledge the agent might not have?
- Is the order of operations explicit or implied?

**Attack 3: Missing steps**
- Walk through the skill as if executing each step. Where do you get stuck?
- Are there branching paths that aren't covered?
- What happens if a prerequisite tool/file/config is missing?
- Are error recovery steps included?

**Attack 4: Hallucination risk**
- Does the skill ask the agent to "generate" content that should be verified?
- Are there places where the agent might invent facts instead of looking them up?
- Does the skill reference specific URLs, file paths, or commands that might change?
- Are verification steps included, or is the skill all "do" and no "check"?

**Attack 5: Context pollution**
- Is the skill too long? (Will it eat context budget when loaded?)
- Does it duplicate information already in the system prompt?
- Are there sections that only apply in specific situations but are always loaded?

### Plugins (Python packages)

**Attack 1: Error handling**
- What happens if every handler receives malformed input?
- What happens if `args` is `None`, `{}`, or missing required keys?
- What happens if a tool handler raises an exception? (It should return error JSON, never raise)
- What happens if the file system is full or the disk is read-only?
- What happens if JSON serialization fails (non-serializable objects)?

**Attack 2: JSON return compliance**
- Does every handler return a JSON string? (Not a dict, not None, not a raw string)
- Does the JSON parse correctly?
- Are error paths also returning JSON strings?
- Is `**kwargs` in every handler signature?

**Attack 3: Hook safety**
- Does the hook crash gracefully? (Errors logged, not propagated)
- Does the hook cause performance degradation? (Timing each hook)
- Does the hook modify state in ways that affect other plugins?
- Does the pre_llm_call hook return None when it should? (Observer-only)

**Attack 4: Thread safety**
- Are shared data structures protected by locks?
- Are there TOCTOU (time-of-check-to-time-of-use) races?
- Are lazy singletons using the proper helpers?
- What happens if two tool calls run simultaneously?

**Attack 5: Resource leaks**
- Are file handles closed properly?
- Are there unbounded lists/dicts that grow forever?
- Does the plugin write to disk on every call? (Should batch or throttle)
- Are there background threads that don't terminate?

### Code

**Attack 1: Boundary testing**
- Empty inputs: `""`, `[]`, `{}`, `None`
- Single-element inputs: `[1]`, `{"a": 1}`
- Maximum-size inputs: very long strings, large lists
- Off-by-one: index 0, index -1, index len-1, index len

**Attack 2: Unicode and encoding**
- Multi-script text: `Lofoten — 洛福滕 — Лофотенские`
- Emoji: `🏔️ fjord 🐟`
- Zero-width characters and RTL text
- Invalid UTF-8 sequences

**Attack 3: Concurrent access**
- Two threads calling the same function simultaneously
- File reads while another thread writes
- Shared state modification during iteration

**Attack 4: Resource exhaustion**
- What happens at 10x, 100x, 1000x normal load?
- Memory usage growth over time
- File handle count growth
- Timeout behavior

### Blog Posts / Content

**Attack 1: Fact verification**
- Pick 3 random claims and verify each against a primary source
- Check all dates: are they correct? Are they in the right format?
- Check all numbers: are they measured or estimated? Are estimates marked?
- Check all names: are they spelled correctly?

**Attack 2: Link integrity**
- Do all URLs resolve? (curl each one)
- Are links pointing to the correct destination?
- Do internal links (to other blog posts) use the correct slugs?

**Attack 3: Template hazards**
- Did a find-replace produce wrong content? (Check for leftover placeholders)
- Is the author name correct? Is the date correct?
- Is the hero image present and referenced correctly?

**Attack 4: Build verification**
- Does the post build without TypeScript errors?
- Is the HTML artifact present after build?
- Does the live URL return 200?

## Edge Case Discovery Methodology

### Systematic Edge Case Generation

For every input parameter, generate:

| Category | Example Values |
|----------|---------------|
| Empty | `""`, `None`, `{}`, `[]`, `0`, `false` |
| Boundary | `1`, `-1`, `MAX_INT`, `0.0`, `1.0` |
| Malformed | `"null"`, `"undefined"`, `"{not json}"`, `"   "` |
| Unicode | `"café"`, `"日本語"`, `"🏔️"`, `"\x00\x01\x02"` |
| Oversized | `"x" * 10000`, `list(range(100000))` |
| Wrong type | String where number expected, list where dict expected |
| Injection | `"'; DROP TABLE--"`, `"<script>alert(1)</script>"` |
| Concurrent | Same call from 2+ threads simultaneously |

### Running the Tests

For each edge case:
1. Call the function/tool with the edge case input
2. Record: did it return a valid JSON string? Did it crash? Did it hang?
3. Classify: PASS (handled gracefully), FAIL (returned bad data), CRASH (exception/timeout)
4. For each FAIL or CRASH: write a fix, re-test

## Red-Team Prompts

Specific adversarial prompts to run against your own work:

### For Skills
1. "Follow this skill step by step with NO additional tools. Where do you get stuck?"
2. "What if the file/tool/API referenced in step 3 doesn't exist?"
3. "What would a malicious user do if they could inject content into this skill?"
4. "Does this skill work on a fresh system with no prior context?"

### For Plugins
1. "Call every tool with `{}` as args. What breaks?"
2. "Call every tool with `None` for every parameter. What breaks?"
3. "Send a 100KB string to every text parameter. What breaks?"
4. "What happens if the plugin's data directory doesn't exist?"
5. "What happens if the plugin's data file is corrupted JSON?"

### For Content
1. "Open the page at 3 random URLs. Do they all load correctly?"
2. "Check every number in the post against its source."
3. "Does the post make any claim you can't verify?"
4. "Did you use find-replace for any content? Check every instance."

## Sign-Off Criteria

Before shipping, ALL of these must pass:

### Skills
- [ ] Frontmatter has all required fields
- [ ] Description is ≤ 57 characters (or you've accepted the truncation)
- [ ] A fresh agent can follow the instructions without asking questions
- [ ] All referenced file paths / commands have been verified to exist
- [ ] Error recovery steps are included for critical operations
- [ ] The skill has been loaded and followed end-to-end at least once
- [ ] No content duplicates information in the system prompt unnecessarily

### Plugins
- [ ] Every handler returns a JSON string (verified by calling each one)
- [ ] Every handler accepts `**kwargs`
- [ ] Every handler handles malformed input gracefully (tested with `{}`, `None`, oversized)
- [ ] No handler raises exceptions (all caught and returned as error JSON)
- [ ] Hooks log errors, don't propagate them
- [ ] Thread-safe shared state (locks used for shared data)
- [ ] No unbounded memory growth (lists/dicts have caps)
- [ ] Plugin loads without errors when Hermes starts
- [ ] The `/plugins` command shows the plugin with correct tool/hook counts

### Content
- [ ] Every external fact has been verified against a primary source
- [ ] All URLs return HTTP 200
- [ ] The build succeeds without new TypeScript errors
- [ ] The HTML artifact exists for new posts
- [ ] The live URL returns 200
- [ ] No template find-replace artifacts remain
- [ ] Author name and date are correct
- [ ] Hero image is present and referenced correctly

## Integration with Other Skills

- **agent-self-assessment** — Use assessment results to prioritize what to harden first
- **research-synthesis** — Use synthesis workflow for content that needs oppositional review
- **skill-forge** — Automated validation tools to catch structural issues quickly
- **plan** — Include oppositional review as an explicit step in implementation plans