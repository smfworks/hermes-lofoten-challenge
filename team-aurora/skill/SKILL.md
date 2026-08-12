---
name: research-synthesis
description: "Structured workflow for transforming raw research material into polished, cited, creative content. Use when writing blog posts, reports, or articles based on research."
version: 1.0.0
author: Nemo (Team Aurora)
license: MIT
metadata:
  hermes:
    tags: [research, writing, synthesis, citation, content-creation]
    category: research
---

# Research Synthesis

A structured workflow for transforming raw research material into polished, cited, creative content. Inspired by the Lofoten stockfish tradition — raw material (cod) is transformed through a patient, structured process (air-drying for months) into a product of lasting value (stockfish) that connects the producer to a global market.

## When to Use

- When you have raw research notes and need to produce a blog post, report, or article
- When asked to write content backed by research
- When you need to weave factual material into technical writing naturally
- When producing a literature review, country analysis, or thematic deep-dive

## The Synthesis Pipeline

### Stage 1: Inventory and Triage

Before writing anything, organize what you have:

1. **Collect all sources** — list every document, URL, paper, and note
2. **Categorize by theme** — group sources into thematic clusters
3. **Rate source quality** — primary (official docs, peer-reviewed) vs secondary (news, blogs) vs tertiary (Wikipedia, aggregators)
4. **Identify gaps** — what do you NOT have? Flag missing facts that need verification

### Stage 2: Thematic Extraction

For each theme cluster:

1. **Extract key facts** — specific names, dates, numbers, locations
2. **Extract narratives** — stories, sequences, cause-and-effect chains
3. **Extract tensions** — conflicts, debates, competing perspectives
4. **Extract metaphors** — natural analogies, cultural touchstones, visual imagery
5. **Note sourcing** — which source provided each fact? Tag everything

### Stage 3: Narrative Architecture

Decide on the structure before writing a single paragraph:

| Structure Type | When to Use | Example |
|---------------|-------------|---------|
| **Chronological** | History, evolution, development over time | "From Stone Age fishing to Viking longhouses to modern overtourism" |
| **Thematic** | Multiple facets of a single subject | "Geology, fishing culture, Sámi influences, modern challenges" |
| **Tension-driven** | Conflicts and their resolutions | "Tradition vs tourism, fishing vs aquaculture, oil vs environment" |
| **Journey** | Following a path through material | "From Oslo to Lofoten: what the landscape teaches about systems" |
| **Problem-solution** | Frame a problem, present solutions | "Agent observability gaps → session-observability plugin" |

### Stage 4: Integration — Weaving Research into Writing

This is the hardest part. The goal is **seamless integration** — research that informs without interrupting, that adds texture without decoration.

#### Principles

1. **Research serves the narrative, not the other way around** — Don't dump facts. Select the facts that advance your argument or illustrate your point.

2. **Specificity over generality** — "Lofoten has beautiful mountains" is decoration. "Higravstinden rises 1,161 meters directly from the sea on Austvågøya" is research.

3. **Show the source's character** — Don't just extract information; capture the *way* the source thinks about the subject. A BBC Travel article and a Wikipedia article about the same place have different textures.

4. **Let tensions breathe** — If the research reveals a conflict (e.g., tourism vs tradition), present both sides. Don't flatten the complexity.

5. **Metaphor from material** — The best metaphors come from the research itself, not imposed from outside. If you're writing about Lofoten, the maelstrom (Moskstraumen) is a better metaphor for system complexity than any generic "turbulence" you might invent.

6. **Don't force it** — If the connection between research and your topic feels strained, it probably is. Either find a genuine connection or leave the research in the background.

#### Integration Patterns

**Pattern 1: The Opening Anchor**
Start with a specific, vivid detail from the research that sets the scene:
> "At 68°N, 300 kilometers inside the Arctic Circle, Lofoten's mountains rise directly from the sea — horst blocks uplifted 400 million years ago in the Caledonian orogeny, carved by glaciers into the jagged wall that defines the archipelago's visual identity."

**Pattern 2: The Structural Analogy**
Use the research as a structural metaphor that recurs throughout the piece:
> "The stockfish trade — cod gutted and hung on wooden racks to dry in the Arctic wind for three months — is a model of patient transformation. Raw material becomes product through a structured process that cannot be rushed. Building a plugin is the same: raw capability must be shaped through testing, drying out the bugs, before it's ready for export."

**Pattern 3: The Contrast and Compare**
Use research to provide perspective on your own work:
> "Lofoten's 25,000 permanent residents host one million annual tourists — a 40:1 ratio that strains infrastructure and threatens the very qualities that attract visitors. The session-observability plugin faces a similar challenge: passive monitoring must not become so heavy that it degrades the session it's supposed to observe."

**Pattern 4: The Historical Echo**
Connect a historical pattern to a contemporary engineering challenge:
> "The rorbu cabins — red wooden huts on stilts over the water — were built for visiting fishermen who needed shelter during the winter cod season. They've been continuously useful for 1,000 years because they were designed for a specific need, built simply, and adapted as that need changed. Good plugins follow the same principle."

### Stage 5: Citation and Verification

Every external fact must be traceable:

1. **Inline attribution** — "According to Wikipedia..." or "BBC Travel reports that..."
2. **Sources section** — List all sources with URLs at the end
3. **Verification notes** — For technical posts, add a verification section documenting how facts were checked
4. **Distinguish measurement from claim** — "The vendor claims X" vs "Our tests measured Y"
5. **Mark estimates** — Use ~ for approximate values. Say "approximately" explicitly.

### Stage 6: Quality Checklist

Before publishing, verify:

- [ ] Every external fact has a source
- [ ] Sources are primary where possible (official docs, peer-reviewed papers)
- [ ] No facts are fabricated or "plausibly invented"
- [ ] The narrative has a clear arc (not just a list of facts)
- [ ] Research integration feels natural, not forced
- [ ] At least one specific detail (name, date, number) per major claim
- [ ] Tensions and conflicts are presented fairly
- [ ] The piece says something new, not just regurgitates sources
- [ ] The conclusion connects back to the opening
- [ ] Technical accuracy is verified by running code, not assumed

## Output Templates

### Blog Post Template
```markdown
# [Title]

**By [Author], [Role], SMF Works**

[Opening: vivid detail from research that sets the scene]

## [Section 1: The Problem/Question]

[Body: what we're building and why, with research anchor]

## [Section 2: The Approach]

[Body: how we built it, with structural analogy from research]

## [Section 3: Results]

[Body: what happened, with tables and data]

## [Section 4: Analysis]

[Body: what it means, with contrast-and-compare from research]

## [Section 5: What's Next]

[Body: future work, with forward-looking research connection]

## Verification notes

[How facts were verified]

## Sources

[All sources with URLs]
```

### Report Template
```markdown
# [Report Title]

## Executive Summary
[2-3 sentence overview]

## Methodology
[How research was conducted]

## Findings
### Theme 1: [Name]
[Findings with sources]

### Theme 2: [Name]
[Findings with sources]

## Analysis
[Cross-cutting analysis]

## Recommendations
[Actionable items]

## Sources
[Complete source list]
```

## Common Pitfalls

| Pitfall | What It Looks Like | Fix |
|---------|-------------------|-----|
| Research dumping | Paragraphs of undigested facts | Select only facts that advance the narrative |
| Forced integration | "Just as Lofoten has mountains, our plugin has features" | Find genuine structural similarities, not surface ones |
| Source laundering | Facts presented without attribution | Tag every fact with its source |
| Decoration | Research mentioned once, never connected to the work | Use research as structural metaphor, not opening ornament |
| Verification skip | "Lofoten has X" without checking | Verify every external fact independently |
| Narrative absence | List of findings with no story | Decide on an arc before writing |