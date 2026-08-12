# Hermes Plugin: Skill Gap Analyzer

> **By Team Stockfish** — Named for stockfish (tørrfisk), the air-dried cod that has been Lofoten's primary export for over 1000 years. Viking Age cod bones from Lofoten have been found in Haithabu, Germany (800–1066 AD), proving a stockfish trade network stretching over 1000 miles. Just as stockfish production involves examining each fish for quality and identifying gaps in the drying process, this plugin examines the skill library for quality and identifies gaps in coverage. The stockfish trade connected Lofoten to Europe; this plugin connects individual skills to the broader skill ecosystem.

## What It Does

**hermes-plugin-skill-gap-analyzer** is a skill library analysis plugin for Hermes Agent that scans skill directories, parses `SKILL.md` frontmatter, and identifies coverage gaps — all without affecting agent behavior. It hooks into the `on_session_start` and `on_skill_lifecycle` hooks to track context, and exposes three tools for the agent to analyze its own skill ecosystem:

- `skill_gap_scan` — scan skill directories and return coverage analysis
- `skill_gap_report` — generate a detailed gap report with recommendations
- `skill_similarity` — find skills that are potential duplicates or overlapping

Scan results are stored in a lightweight SQLite database at `~/.hermes/skill_gap.db` (profile-aware).

## Why We Built It

Hermes agents rely on a library of skills to extend their capabilities, but there is no built-in way to assess the quality and coverage of that library. This creates several blind spots:

1. **Thin categories** — A skill category with only one or two skills offers limited capability. Without analysis, these go unnoticed.
2. **Overly narrow skills** — Skills with very short descriptions and no tags are hard to discover and understand.
3. **Missing capabilities** — Core workflow areas like testing, deployment, or monitoring may have no skill coverage at all.
4. **Potential duplicates** — Two skills with highly similar descriptions may overlap in functionality, creating confusion about which to use.
5. **No recommendations** — Without systematic analysis, it's unclear where new skills should be created to fill gaps.

Stockfish production is the same: each fish must be examined individually for quality, and gaps in the drying process must be identified before the fish is shipped. This plugin brings that same quality-control mindset to the skill library.

## How It Works

### Skill Scanning

The plugin recursively discovers all `SKILL.md` files under the configured skill directories:

1. `~/.hermes/skills/` — user-installed skills
2. `~/.hermes/profiles/*/skills/` — profile-specific skills
3. In-repo `skills/` directory (if `HERMES_HOME` points to a repo)

Each `SKILL.md` is parsed for YAML frontmatter containing `name`, `description`, `tags`, and other metadata. Categories are inferred from directory structure (e.g., `github/github-auth/SKILL.md` → category `github`).

### Gap Analysis

Four types of gaps are identified:

- **Thin categories** — Categories with fewer than `min_category_size` skills (default: 3)
- **Narrow skills** — Skills with descriptions shorter than `narrow_desc_threshold` characters (default: 30) or no tags
- **Missing capabilities** — Common capability areas (testing, deployment, monitoring, etc.) with no tag coverage
- **Overlapping skills** — Skill pairs with Jaccard description similarity above `similarity_threshold` (default: 0.6)

### Recommendations

The plugin generates prioritized recommendations:

- **Critical** — Empty skill library
- **High** — Thin categories, small library (< 5 skills)
- **Medium** — Missing capabilities, narrow skills
- **Low** — Potential duplicates

## Installation

```bash
# Clone or copy to plugins directory
cp -r hermes-plugin-skill-gap-analyzer ~/.hermes/plugins/skill-gap-analyzer

# Enable the plugin
hermes config set plugins.enabled '["skill-gap-analyzer"]'

# Verify
hermes plugins list
```

## Configuration

```yaml
# config.yaml
plugins:
  entries:
    skill-gap-analyzer:
      # Maximum description length to store
      max_desc_length: 2000
      # Jaccard similarity threshold for overlap detection (0.0–1.0)
      similarity_threshold: 0.6
      # Minimum skills per category before it's flagged as "thin"
      min_category_size: 3
      # Description length below which a skill is "narrow" (in characters)
      narrow_desc_threshold: 30
```

## Usage Examples

### Scan the skill library

```json
// tool call: skill_gap_scan
{}
```

Returns:
```json
{
  "scan_id": "abc-123",
  "total_skills": 56,
  "total_categories": 12,
  "thin_categories_count": 4,
  "narrow_skills_count": 3,
  "missing_capabilities_count": 2,
  "overlaps_count": 5,
  "recommendations_count": 14
}
```

### Generate a detailed report

```json
// tool call: skill_gap_report
{"rescan": true}
```

### Find overlapping skills

```json
// tool call: skill_similarity
{"threshold": 0.5}
```

### Find skills similar to a specific one

```json
// tool call: skill_similarity
{"skill_name": "github-auth", "threshold": 0.3}
```

## Database Schema

Results are stored in three SQLite tables:

- `scans` — scan summaries (scan_id, totals, timestamp)
- `skills` — individual skill metadata per scan
- `gaps` — identified gaps and recommendations per scan

All writes are thread-safe via a global lock, and database failures are handled gracefully — the plugin never crashes the agent.

## Lofoten Connection

Stockfish (tørrfisk) is unsalted fish, usually cod, dried by cold air and wind on wooden racks (hjell). The drying takes approximately three months, during which the fish loses about 80% of its water content and develops a concentrated flavor and extended shelf life that made it ideal for long-distance trade.

Lofoten's stockfish trade is one of Norway's oldest export industries, dating back to the Viking Age. Archaeological finds of cod bones from Lofoten in Haithabu (Hedeby), Germany — a major Viking trading settlement active from 800 to 1066 AD — prove that stockfish was transported over 1000 miles southward, connecting the Arctic Lofoten islands to the heart of medieval Europe.

The stockfish trade was Norway's largest export industry for centuries, and the Lofoten fishery remains active today. The fish are still examined individually for quality: each one is sorted by grade, with the finest stockfish (prima) destined for export to Italy, where stockfish (stoccafisso) remains a prized ingredient in traditional cuisine.

The connection: just as each fish in a stockfish catch must be examined for quality and the drying process checked for gaps, each skill in a Hermes agent's library must be examined for quality and the coverage checked for gaps. The stockfish trade connected individual fishermen to a continent-spanning network; this plugin connects individual skills to the broader skill ecosystem, identifying where the library is thin, where skills overlap, and where new capabilities are needed.

## License

MIT