"""
Skill Gap Analyzer Plugin for Hermes Agent
============================================

Examines the skill library for quality and identifies gaps in coverage —
named for stockfish (tørrfisk), the air-dried cod that has been Lofoten's
primary export for over 1000 years. Just as stockfish production involves
examining each fish for quality and identifying gaps in the drying process,
this plugin examines each skill for quality and identifies gaps in coverage.

Hooks: on_session_start, on_skill_lifecycle
Tools: skill_gap_scan, skill_gap_report, skill_similarity
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_DESC_LENGTH = 2000
DEFAULT_SIMILARITY_THRESHOLD = 0.6
DEFAULT_MIN_CATEGORY_SIZE = 3
DEFAULT_NARROW_DESC_THRESHOLD = 30  # Skills with descriptions shorter than this are "narrow"

# Canonical skill directories to scan
DEFAULT_SKILL_DIRS = [
    "~/.hermes/skills",
    "~/.hermes/profiles/*/skills",
]

# In-repo skills directory (relative to HERMES_HOME or repo root)
IN_REPO_SKILLS_MARKER = "skills"


def _get_hermes_home() -> Path:
    """Resolve the active Hermes home. Explicit HERMES_HOME wins."""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.path.expanduser("~/.hermes"))


def _get_gap_db_path() -> Path:
    """Gap analysis DB lives inside the profile directory."""
    return _get_hermes_home() / "skill_gap.db"


def _get_skill_dirs() -> List[Path]:
    """Resolve all skill directories to scan.

    Scans:
      1. ~/.hermes/skills/ (user-installed skills)
      2. ~/.hermes/profiles/*/skills/ (profile-specific skills)
      3. In-repo skills/ directory if HERMES_HOME points to a repo
    """
    dirs: List[Path] = []
    home = _get_hermes_home()

    # Primary skills directory
    primary = home / "skills"
    if primary.exists():
        dirs.append(primary)

    # Current-home skills only. Do not walk sibling profiles unless opted in —
    # default ~/.hermes/profiles/* would otherwise scan every agent.
    if os.environ.get("HERMES_SCAN_ALL_PROFILES") == "1":
        profiles_dir = home / "profiles"
        if profiles_dir.exists():
            for profile in profiles_dir.iterdir():
                if profile.is_dir():
                    pskills = profile / "skills"
                    if pskills.exists():
                        dirs.append(pskills)

    # In-repo skills (if HERMES_HOME is the repo root)
    repo_skills = home / IN_REPO_SKILLS_MARKER
    if repo_skills.exists() and repo_skills not in dirs:
        dirs.append(repo_skills)

    return dirs


# Thread-local storage
_local = threading.local()

# Global config
_config: Dict[str, Any] = {}

# Session tracking
_current_session_id: Optional[str] = None


def _get_config_value(key: str, default: Any = None) -> Any:
    """Read a config value from the global _config dict."""
    return _config.get(key, default)


# ---------------------------------------------------------------------------
# Skill Parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML-like frontmatter from a SKILL.md file.

    Handles simple key: value pairs and basic inline lists.
    Does not require a YAML library — uses lightweight parsing.
    """
    fm: Dict[str, Any] = {}
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return fm

    block = match.group(1)
    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # key: value
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # Strip quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            # Parse inline list [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                items = [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
                fm[key] = items
            else:
                fm[key] = value
    return fm


def _parse_skill_file(skill_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a single SKILL.md file and return its metadata.

    Returns None if the file cannot be read or has no frontmatter.
    """
    try:
        content = skill_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None

    fm = _parse_frontmatter(content)
    if not fm:
        return None

    name = fm.get("name", skill_path.parent.name)
    description = fm.get("description", "")
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Also check metadata.hermes.tags (nested structure used by some skills)
    # Since our parser is flat, tags might appear under "metadata" — handle both
    raw_tags = fm.get("tags", [])
    if not raw_tags:
        # Try to find tags in the raw content
        tag_match = re.search(r"tags:\s*\[([^\]]+)\]", content)
        if tag_match:
            raw_tags = [t.strip().strip('"').strip("'") for t in tag_match.group(1).split(",") if t.strip()]

    # Determine category from parent directory
    category = skill_path.parent.parent.name if skill_path.parent.parent.name != "skills" else "root"

    return {
        "name": name,
        "description": description,
        "tags": raw_tags if isinstance(raw_tags, list) else [str(raw_tags)],
        "category": category,
        "path": str(skill_path.parent),
        "file": str(skill_path),
        "description_length": len(description),
        "content_size": len(content),
    }


def _scan_skill_directories(dirs: List[Path]) -> List[Dict[str, Any]]:
    """Scan skill directories and return parsed skill metadata.

    Recursively finds all SKILL.md files under each directory.
    Handles nested categories (e.g., github/github-auth/SKILL.md).
    """
    skills: List[Dict[str, Any]] = []
    seen_paths: Set[str] = set()

    for base_dir in dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        for skill_md in base_dir.rglob("SKILL.md"):
            try:
                real_path = str(skill_md.resolve())
            except OSError:
                real_path = str(skill_md)
            if real_path in seen_paths:
                continue
            seen_paths.add(real_path)

            parsed = _parse_skill_file(skill_md)
            if parsed:
                # Determine category: walk up from the skill dir to find the
                # category (first directory under the base skills dir)
                rel = skill_md.parent
                try:
                    rel = skill_md.parent.relative_to(base_dir)
                    parts = rel.parts
                    if len(parts) > 1:
                        parsed["category"] = parts[0]
                    else:
                        parsed["category"] = "root"
                except ValueError:
                    pass
                parsed["source_dir"] = str(base_dir)
                skills.append(parsed)

    return skills


# ---------------------------------------------------------------------------
# Gap Analysis
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase word tokens for similarity comparison."""
    return set(re.findall(r"\b[a-z][a-z0-9_-]+\b", text.lower()))


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    intersection = a & b
    return len(intersection) / len(union)


def _analyze_category_coverage(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze category coverage — identify thin and missing categories."""
    category_counts: Dict[str, int] = {}
    category_skills: Dict[str, List[str]] = {}

    for skill in skills:
        cat = skill.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        category_skills.setdefault(cat, []).append(skill["name"])

    min_size = _get_config_value("min_category_size", DEFAULT_MIN_CATEGORY_SIZE)

    thin_categories = [
        {"category": cat, "count": cnt, "skills": category_skills[cat]}
        for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1])
        if cnt < min_size
    ]

    return {
        "total_categories": len(category_counts),
        "category_counts": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "thin_categories": thin_categories,
    }


def _identify_narrow_skills(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify skills that are overly narrow (very short descriptions, no tags)."""
    threshold = _get_config_value("narrow_desc_threshold", DEFAULT_NARROW_DESC_THRESHOLD)
    narrow = []
    for skill in skills:
        desc = skill.get("description", "")
        tags = skill.get("tags", [])
        issues = []
        if len(desc) < threshold:
            issues.append(f"short_description ({len(desc)} chars)")
        if not tags:
            issues.append("no_tags")
        if issues:
            narrow.append({
                "name": skill["name"],
                "category": skill.get("category", "unknown"),
                "issues": issues,
                "description_length": len(desc),
            })
    return narrow


def _identify_missing_capabilities(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify potentially missing capabilities based on tag and category analysis."""
    all_tags: Dict[str, int] = {}
    for skill in skills:
        for tag in skill.get("tags", []):
            tag_lower = tag.lower().strip()
            if tag_lower:
                all_tags[tag_lower] = all_tags.get(tag_lower, 0) + 1

    # Common capability areas that a well-rounded skill library should cover
    expected_areas = [
        "testing", "deployment", "monitoring", "security", "documentation",
        "code-review", "ci-cd", "debugging", "refactoring", "performance",
        "data-analysis", "automation", "git", "docker", "api",
    ]

    existing_tags_lower = set(all_tags.keys())
    missing = []
    for area in expected_areas:
        # Check if any tag contains the area keyword
        found = any(area in tag or tag in area for tag in existing_tags_lower)
        if not found:
            missing.append({
                "capability": area,
                "reason": "no_skill_tags_cover_this_area",
                "suggestion": f"Create a skill for {area} workflows",
            })

    return missing


def _find_overlapping_skills(
    skills: List[Dict[str, Any]], threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Find skills that are potential duplicates or overlapping.

    Uses Jaccard similarity on tokenized descriptions.
    """
    if threshold is None:
        threshold = _get_config_value("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD)

    # Pre-tokenize all descriptions
    tokenized = []
    for skill in skills:
        desc = skill.get("description", "") + " " + skill.get("name", "")
        tokens = _tokenize(desc)
        tokenized.append((skill, tokens))

    overlaps = []
    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            skill_a, tokens_a = tokenized[i]
            skill_b, tokens_b = tokenized[j]
            sim = _jaccard_similarity(tokens_a, tokens_b)
            if sim >= threshold:
                overlaps.append({
                    "skill_a": skill_a["name"],
                    "skill_b": skill_b["name"],
                    "category_a": skill_a.get("category", "unknown"),
                    "category_b": skill_b.get("category", "unknown"),
                    "similarity": round(sim, 3),
                })

    # Sort by similarity descending
    overlaps.sort(key=lambda x: -x["similarity"])
    return overlaps


def _generate_recommendations(
    coverage: Dict[str, Any],
    narrow: List[Dict[str, Any]],
    missing: List[Dict[str, Any]],
    overlaps: List[Dict[str, Any]],
    total_skills: int,
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations based on gap analysis."""
    recommendations = []

    # Thin categories
    for tc in coverage.get("thin_categories", []):
        recommendations.append({
            "priority": "high",
            "type": "thin_category",
            "category": tc["category"],
            "current_count": tc["count"],
            "recommendation": (
                f"Category '{tc['category']}' has only {tc['count']} skill(s). "
                f"Consider adding more skills to this category for better coverage."
            ),
        })

    # Missing capabilities
    for mc in missing:
        recommendations.append({
            "priority": "medium",
            "type": "missing_capability",
            "capability": mc["capability"],
            "recommendation": mc["suggestion"],
        })

    # Overlapping skills
    for ov in overlaps[:10]:  # Top 10 overlaps
        recommendations.append({
            "priority": "low",
            "type": "potential_duplicate",
            "skills": [ov["skill_a"], ov["skill_b"]],
            "similarity": ov["similarity"],
            "recommendation": (
                f"Skills '{ov['skill_a']}' and '{ov['skill_b']}' have "
                f"{ov['similarity']*100:.0f}% description similarity. "
                f"Consider merging or differentiating them."
            ),
        })

    # Narrow skills
    for ns in narrow:
        recommendations.append({
            "priority": "medium",
            "type": "narrow_skill",
            "skill": ns["name"],
            "issues": ns["issues"],
            "recommendation": (
                f"Skill '{ns['name']}' has issues: {', '.join(ns['issues'])}. "
                f"Consider enriching its description and adding tags."
            ),
        })

    # Overall assessment
    if total_skills == 0:
        recommendations.append({
            "priority": "critical",
            "type": "empty_library",
            "recommendation": "No skills found. Install skills to build your skill library.",
        })
    elif total_skills < 5:
        recommendations.append({
            "priority": "high",
            "type": "small_library",
            "current_count": total_skills,
            "recommendation": (
                f"Only {total_skills} skills found. Consider expanding the library "
                f"for better agent capability coverage."
            ),
        })

    return recommendations


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()


def _safe_get_db() -> Optional[sqlite3.Connection]:
    """Try to get a DB connection, return None on failure."""
    try:
        db_path = _get_gap_db_path()
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            category TEXT,
            path TEXT,
            file TEXT,
            source_dir TEXT,
            description_length INTEGER,
            content_size INTEGER,
            scanned_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_skills_scan ON skills(scan_id);
        CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
        CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);

        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            session_id TEXT,
            total_skills INTEGER,
            total_categories INTEGER,
            thin_categories_count INTEGER,
            narrow_skills_count INTEGER,
            missing_capabilities_count INTEGER,
            overlaps_count INTEGER,
            scanned_at REAL NOT NULL,
            summary TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_scans_time ON scans(scanned_at);

        CREATE TABLE IF NOT EXISTS gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL,
            gap_type TEXT NOT NULL,
            priority TEXT,
            details TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gaps_scan ON gaps(scan_id);
        CREATE INDEX IF NOT EXISTS idx_gaps_type ON gaps(gap_type);
    """)
    conn.commit()


def _store_scan_results(
    scan_id: str,
    session_id: Optional[str],
    skills: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    narrow: List[Dict[str, Any]],
    missing: List[Dict[str, Any]],
    overlaps: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
    timestamp: float,
) -> None:
    """Store scan results into the database."""
    with _db_lock:
        conn = _safe_get_db()
        if conn is None:
            return
        try:
            _init_db(conn)

            # Store scan summary
            summary = {
                "total_categories": coverage.get("total_categories", 0),
                "category_counts": coverage.get("category_counts", {}),
            }
            conn.execute(
                """INSERT OR REPLACE INTO scans
                   (scan_id, session_id, total_skills, total_categories,
                    thin_categories_count, narrow_skills_count,
                    missing_capabilities_count, overlaps_count, scanned_at, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scan_id, session_id, len(skills),
                    coverage.get("total_categories", 0),
                    len(coverage.get("thin_categories", [])),
                    len(narrow), len(missing), len(overlaps),
                    timestamp, json.dumps(summary, ensure_ascii=False),
                ),
            )

            # Store skills
            for skill in skills:
                conn.execute(
                    """INSERT INTO skills
                       (scan_id, name, description, tags, category, path, file,
                        source_dir, description_length, content_size, scanned_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        scan_id, skill["name"], skill.get("description", ""),
                        json.dumps(skill.get("tags", []), ensure_ascii=False),
                        skill.get("category", "unknown"),
                        skill.get("path", ""), skill.get("file", ""),
                        skill.get("source_dir", ""),
                        skill.get("description_length", 0),
                        skill.get("content_size", 0),
                        timestamp,
                    ),
                )

            # Store gaps (recommendations)
            for rec in recommendations:
                gap_type = rec.get("type", "unknown")
                conn.execute(
                    """INSERT INTO gaps
                       (scan_id, gap_type, priority, details, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        scan_id, gap_type,
                        rec.get("priority", "low"),
                        json.dumps(rec, ensure_ascii=False),
                        timestamp,
                    ),
                )

            conn.commit()
        except Exception:
            pass  # Never let storage failure break the agent
        finally:
            conn.close()


def _get_latest_scan_id(conn: sqlite3.Connection) -> Optional[str]:
    """Get the scan_id of the most recent scan."""
    row = conn.execute(
        "SELECT scan_id FROM scans ORDER BY scanned_at DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def _on_session_start(**kwargs: Any) -> None:
    """Track the current session ID for correlating scans."""
    global _current_session_id
    _current_session_id = kwargs.get("session_id") or str(uuid.uuid4())


def _on_skill_lifecycle(**kwargs: Any) -> None:
    """React to skill installation/removal by invalidating cached scan data.

    When skills are added or removed, the gap analysis may change. We don't
    auto-rescan (that could be expensive), but we log the event so the next
    scan knows the library was modified.
    """
    event = kwargs.get("event", "unknown")
    skill_name = kwargs.get("skill_name", "unknown")
    _local.last_skill_event = {"event": event, "skill_name": skill_name, "time": time.time()}


# ---------------------------------------------------------------------------
# Tool handlers (exposed to the agent)
# ---------------------------------------------------------------------------

def _tool_skill_gap_scan(args: Dict[str, Any], **kw: Any) -> str:
    """Scan skill directories and return coverage analysis.

    Args:
        dirs: Optional list of explicit directories to scan (overrides defaults)
        store: Whether to store results in the database (default: true)
    """
    dirs_arg = args.get("dirs")
    store = args.get("store", True)
    timestamp = time.time()
    scan_id = str(uuid.uuid4())

    # Resolve directories
    if dirs_arg:
        dirs = [Path(d) for d in dirs_arg]
    else:
        dirs = _get_skill_dirs()

    # Scan skills
    skills = _scan_skill_directories(dirs)

    # Analyze
    coverage = _analyze_category_coverage(skills)
    narrow = _identify_narrow_skills(skills)
    missing = _identify_missing_capabilities(skills)
    overlaps = _find_overlapping_skills(skills)
    recommendations = _generate_recommendations(
        coverage, narrow, missing, overlaps, len(skills)
    )

    # Store results
    if store:
        _store_scan_results(
            scan_id, _current_session_id, skills,
            coverage, narrow, missing, overlaps, recommendations,
            timestamp,
        )

    result = {
        "scan_id": scan_id,
        "scanned_at": timestamp,
        "directories_scanned": [str(d) for d in dirs],
        "total_skills": len(skills),
        "total_categories": coverage["total_categories"],
        "category_counts": coverage["category_counts"],
        "thin_categories_count": len(coverage["thin_categories"]),
        "narrow_skills_count": len(narrow),
        "missing_capabilities_count": len(missing),
        "overlaps_count": len(overlaps),
        "recommendations_count": len(recommendations),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def _tool_skill_gap_report(args: Dict[str, Any], **kw: Any) -> str:
    """Generate a detailed gap report with recommendations.

    Args:
        scan_id: Optional scan ID to report on (defaults to latest scan)
        rescan: If true, perform a new scan before generating the report (default: false)
        dirs: Optional list of directories to scan (only if rescan=true)
    """
    rescan = args.get("rescan", False)
    dirs_arg = args.get("dirs")

    # If rescan requested, perform a new scan first
    if rescan:
        scan_args = {}
        if dirs_arg:
            scan_args["dirs"] = dirs_arg
        scan_result = json.loads(_tool_skill_gap_scan(scan_args, **kw))
        scan_id = scan_result.get("scan_id")
    else:
        scan_id = args.get("scan_id")

    with _db_lock:
        conn = _safe_get_db()
        if conn is None:
            return json.dumps({"error": "gap analysis database unavailable"})
        try:
            _init_db(conn)

            # Find the scan to report on
            if not scan_id:
                scan_id = _get_latest_scan_id(conn)

            if not scan_id:
                return json.dumps({
                    "error": "no_scan_found",
                    "message": "No scan found. Run skill_gap_scan first or use rescan=true.",
                })

            # Get scan summary
            scan_row = conn.execute(
                "SELECT * FROM scans WHERE scan_id = ?", (scan_id,)
            ).fetchone()
            if not scan_row:
                return json.dumps({"error": "scan_not_found", "scan_id": scan_id})

            # Get skills from this scan
            skill_rows = conn.execute(
                "SELECT name, description, tags, category, path, description_length FROM skills WHERE scan_id = ?",
                (scan_id,),
            ).fetchall()

            # Get gaps from this scan
            gap_rows = conn.execute(
                "SELECT gap_type, priority, details FROM gaps WHERE scan_id = ? ORDER BY priority",
                (scan_id,),
            ).fetchall()

            # Get categories with counts
            cat_rows = conn.execute(
                """SELECT category, COUNT(*) as count FROM skills
                   WHERE scan_id = ? GROUP BY category ORDER BY count DESC""",
                (scan_id,),
            ).fetchall()

            # If no stored skills but rescan wasn't requested, try to re-scan live
            if not skill_rows and not rescan:
                # Fall back to live scan for the report
                dirs = _get_skill_dirs()
                skills = _scan_skill_directories(dirs)
                coverage = _analyze_category_coverage(skills)
                narrow = _identify_narrow_skills(skills)
                missing = _identify_missing_capabilities(skills)
                overlaps = _find_overlapping_skills(skills)
                recommendations = _generate_recommendations(
                    coverage, narrow, missing, overlaps, len(skills)
                )

                # Get skills by category
                by_category: Dict[str, List[str]] = {}
                for s in skills:
                    cat = s.get("category", "unknown")
                    by_category.setdefault(cat, []).append(s["name"])

                result = {
                    "scan_id": scan_id,
                    "scanned_at": scan_row["scanned_at"],
                    "total_skills": len(skills),
                    "total_categories": len(by_category),
                    "categories": {k: {"count": len(v), "skills": v} for k, v in sorted(by_category.items())},
                    "thin_categories": coverage["thin_categories"],
                    "narrow_skills": narrow,
                    "missing_capabilities": missing,
                    "overlapping_skills": overlaps,
                    "recommendations": recommendations,
                    "source": "live_fallback",
                }
                return json.dumps(result, indent=2, ensure_ascii=False)

            # Build report from DB data
            categories = {}
            for row in cat_rows:
                categories[row["category"]] = {"count": row["count"]}

            # Populate skills per category
            for row in skill_rows:
                cat = row["category"]
                if cat not in categories:
                    categories[cat] = {"count": 0, "skills": []}
                if "skills" not in categories[cat]:
                    categories[cat]["skills"] = []
                categories[cat]["skills"].append(row["name"])

            # Parse gap details
            recommendations = []
            for row in gap_rows:
                try:
                    recommendations.append(json.loads(row["details"]))
                except (json.JSONDecodeError, TypeError):
                    pass

            result = {
                "scan_id": scan_id,
                "scanned_at": scan_row["scanned_at"],
                "total_skills": scan_row["total_skills"],
                "total_categories": scan_row["total_categories"],
                "thin_categories_count": scan_row["thin_categories_count"],
                "narrow_skills_count": scan_row["narrow_skills_count"],
                "missing_capabilities_count": scan_row["missing_capabilities_count"],
                "overlaps_count": scan_row["overlaps_count"],
                "categories": categories,
                "recommendations": recommendations,
                "source": "database",
            }
        except Exception as e:
            result = {"error": str(e)}
        finally:
            conn.close()

    return json.dumps(result, indent=2, ensure_ascii=False)


def _tool_skill_similarity(args: Dict[str, Any], **kw: Any) -> str:
    """Find skills that are potential duplicates or overlapping.

    Args:
        threshold: Similarity threshold from 0.0 to 1.0 (default: 0.6)
        dirs: Optional list of directories to scan (overrides defaults)
        skill_name: Optional — find skills similar to this specific skill
    """
    threshold = args.get("threshold")
    dirs_arg = args.get("dirs")
    target_skill = args.get("skill_name")

    # Resolve directories
    if dirs_arg:
        dirs = [Path(d) for d in dirs_arg]
    else:
        dirs = _get_skill_dirs()

    # Scan skills
    skills = _scan_skill_directories(dirs)

    if not skills:
        return json.dumps({
            "threshold": threshold or _get_config_value("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
            "total_skills": 0,
            "overlaps": [],
            "message": "No skills found in scanned directories.",
        }, indent=2)

    # If looking for a specific skill, filter
    if target_skill:
        target = None
        for s in skills:
            if s["name"].lower() == target_skill.lower():
                target = s
                break
        if not target:
            return json.dumps({
                "error": "skill_not_found",
                "skill_name": target_skill,
                "available_skills": [s["name"] for s in skills],
            }, indent=2)

        # Compare target against all others
        target_tokens = _tokenize(target.get("description", "") + " " + target["name"])
        similarities = []
        for s in skills:
            if s["name"] == target["name"]:
                continue
            tokens = _tokenize(s.get("description", "") + " " + s["name"])
            sim = _jaccard_similarity(target_tokens, tokens)
            if threshold is None or sim >= threshold:
                similarities.append({
                    "skill": s["name"],
                    "category": s.get("category", "unknown"),
                    "similarity": round(sim, 3),
                })
        similarities.sort(key=lambda x: -x["similarity"])

        result = {
            "target_skill": target["name"],
            "threshold": threshold if threshold is not None else 0.0,
            "total_compared": len(similarities),
            "similar_skills": similarities[:20],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Find all overlapping pairs
    overlaps = _find_overlapping_skills(skills, threshold)

    result = {
        "threshold": threshold if threshold is not None else _get_config_value("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
        "total_skills": len(skills),
        "overlaps_count": len(overlaps),
        "overlaps": overlaps,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register skill gap analyzer hooks and tools with the Hermes plugin context."""
    global _config

    # Load plugin configuration from config.yaml
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        plugin_cfg = (cfg.get("plugins") or {}).get("entries") or {}
        gap_cfg = plugin_cfg.get("skill-gap-analyzer") or {}
        _config = {
            "max_desc_length": gap_cfg.get("max_desc_length", DEFAULT_MAX_DESC_LENGTH),
            "similarity_threshold": gap_cfg.get("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
            "min_category_size": gap_cfg.get("min_category_size", DEFAULT_MIN_CATEGORY_SIZE),
            "narrow_desc_threshold": gap_cfg.get("narrow_desc_threshold", DEFAULT_NARROW_DESC_THRESHOLD),
        }
    except Exception:
        _config = {
            "max_desc_length": DEFAULT_MAX_DESC_LENGTH,
            "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
            "min_category_size": DEFAULT_MIN_CATEGORY_SIZE,
            "narrow_desc_threshold": DEFAULT_NARROW_DESC_THRESHOLD,
        }

    # Register hooks
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_skill_lifecycle", _on_skill_lifecycle)

    # Register tools
    ctx.register_tool(
        name="skill_gap_scan",
        toolset="skill-gap",
        schema={
            "name": "skill_gap_scan",
            "description": (
                "Scan skill directories and return coverage analysis. Discovers all "
                "SKILL.md files under the configured skill directories, parses their "
                "frontmatter, and reports category counts, thin categories, narrow "
                "skills, missing capabilities, and overlapping skills. Results are "
                "stored in a local SQLite database for later reporting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dirs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of directories to scan (overrides defaults)",
                    },
                    "store": {
                        "type": "boolean",
                        "description": "Whether to store results in the database (default: true)",
                        "default": True,
                    },
                },
            },
        },
        handler=lambda args, **kw: _tool_skill_gap_scan(args, **kw),
        description="Scan skill directories and return coverage analysis",
        emoji="🔍",
    )

    ctx.register_tool(
        name="skill_gap_report",
        toolset="skill-gap",
        schema={
            "name": "skill_gap_report",
            "description": (
                "Generate a detailed gap report with recommendations. Uses the most "
                "recent scan results from the database, or can perform a fresh scan. "
                "Includes category breakdowns, thin categories, narrow skills, missing "
                "capabilities, overlapping skills, and prioritized recommendations for "
                "where new skills should be created."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_id": {
                        "type": "string",
                        "description": "Optional scan ID to report on (defaults to latest scan)",
                    },
                    "rescan": {
                        "type": "boolean",
                        "description": "If true, perform a new scan before generating the report (default: false)",
                        "default": False,
                    },
                    "dirs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of directories to scan (only if rescan=true)",
                    },
                },
            },
        },
        handler=lambda args, **kw: _tool_skill_gap_report(args, **kw),
        description="Generate a detailed gap report with recommendations",
        emoji="📋",
    )

    ctx.register_tool(
        name="skill_similarity",
        toolset="skill-gap",
        schema={
            "name": "skill_similarity",
            "description": (
                "Find skills that are potential duplicates or overlapping. Compares "
                "skill descriptions using Jaccard token similarity. Can find all "
                "overlapping pairs or compare a specific skill against the rest of "
                "the library. Use this to identify merge candidates or ensure skill "
                "boundaries are clear."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Similarity threshold from 0.0 to 1.0 (default: 0.6)",
                        "default": 0.6,
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "Optional — find skills similar to this specific skill",
                    },
                    "dirs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of directories to scan (overrides defaults)",
                    },
                },
            },
        },
        handler=lambda args, **kw: _tool_skill_similarity(args, **kw),
        description="Find skills that are potential duplicates or overlapping",
        emoji="📎",
    )

    # Initialize the database on load
    try:
        conn = _safe_get_db()
        if conn:
            _init_db(conn)
            conn.close()
    except Exception:
        pass  # Will be created on first tool call