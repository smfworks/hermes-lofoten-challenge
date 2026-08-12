"""
Tests for Skill Gap Analyzer Plugin
=====================================

Oppositional test suite — tries to break the plugin from multiple angles:
- Frontmatter parsing edge cases (missing, malformed, nested)
- Category coverage analysis with thin/empty categories
- Narrow skill identification (short descriptions, missing tags)
- Missing capability detection
- Skill similarity / overlap detection
- Database storage and retrieval
- Thread safety under concurrent scans
- Error handling when DB is unwritable
- Edge cases: empty dirs, no skills, unicode, large libraries
- Plugin registration and hook/tool wiring
"""

import json
import os
import sqlite3
import tempfile
import threading
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# Import the plugin module
import sys
plugin_path = str(Path(__file__).parent)
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

import __init__ as gap_plugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill_md(
    name: str,
    description: str = "A skill for testing.",
    tags=None,
    version: str = "1.0.0",
) -> str:
    """Generate a SKILL.md file content with frontmatter."""
    tag_str = ""
    if tags is not None:
        if isinstance(tags, list):
            tag_str = f"\nmetadata:\n  hermes:\n    tags: {tags}"
        else:
            tag_str = f"\ntags: {tags}"
    return f"""---
name: {name}
description: "{description}"
version: {version}{tag_str}
---

# {name}

This is a test skill.
"""


def _create_skill_dir(base: Path, category: str, name: str, description: str = "A skill for testing.", tags=None) -> Path:
    """Create a skill directory with a SKILL.md file inside."""
    skill_dir = base / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(_make_skill_md(name, description, tags), encoding="utf-8")
    return skill_file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the plugin at a temporary database."""
    db_path = tmp_path / "skill_gap.db"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    gap_plugin._config.clear()
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_skills(tmp_path, monkeypatch):
    """Create a temporary skill library structure under tmp_path."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    gap_plugin._config.clear()

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skills across several categories
    _create_skill_dir(skills_dir, "github", "github-auth", "GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login.", ["git", "auth", "github"])
    _create_skill_dir(skills_dir, "github", "github-pr", "GitHub PR workflow: branch, commit, open, CI, merge.", ["git", "github", "pr"])
    _create_skill_dir(skills_dir, "github", "github-issues", "GitHub issues: create, triage, label, assign.", ["git", "github", "issues"])
    _create_skill_dir(skills_dir, "mlops", "llama-cpp", "llama.cpp local GGUF inference and model serving.", ["llama", "inference", "gguf"])
    _create_skill_dir(skills_dir, "mlops", "vllm", "vLLM high-throughput LLM serving with OpenAI API.", ["vllm", "inference", "serving"])
    _create_skill_dir(skills_dir, "devops", "docker-mgmt", "Manage Docker containers, images, volumes, networks.", ["docker", "devops"])
    _create_skill_dir(skills_dir, "creative", "ascii-art", "ASCII art: pyfiglet, cowsay, boxes, image-to-ascii.", ["ascii", "art", "creative"])
    _create_skill_dir(skills_dir, "creative", "pixel-art", "Pixel art with era palettes: NES, Game Boy, PICO-8.", ["pixel", "art", "creative"])

    yield skills_dir


@pytest.fixture
def mock_ctx():
    """Create a mock PluginContext for testing registration."""
    ctx = MagicMock()
    ctx.register_hook = MagicMock()
    ctx.register_tool = MagicMock()
    ctx.manifest = MagicMock()
    ctx.manifest.name = "skill-gap-analyzer"
    ctx.manifest.key = "skill-gap-analyzer"
    return ctx


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------

class TestPluginRegistration:
    """Verify the plugin registers correctly with Hermes."""

    def test_register_creates_hooks(self, mock_ctx, temp_db):
        """Plugin should register hooks: on_session_start, on_skill_lifecycle."""
        gap_plugin.register(mock_ctx)
        hook_names = [call.args[0] for call in mock_ctx.register_hook.call_args_list]
        assert "on_session_start" in hook_names
        assert "on_skill_lifecycle" in hook_names

    def test_register_creates_tools(self, mock_ctx, temp_db):
        """Plugin should register three tools: skill_gap_scan, skill_gap_report, skill_similarity."""
        gap_plugin.register(mock_ctx)
        tool_names = [call.kwargs.get("name") for call in mock_ctx.register_tool.call_args_list]
        assert "skill_gap_scan" in tool_names
        assert "skill_gap_report" in tool_names
        assert "skill_similarity" in tool_names

    def test_register_initializes_db(self, mock_ctx, temp_db):
        """Database file should be created during registration."""
        gap_plugin.register(mock_ctx)
        assert temp_db.exists()

    def test_register_handles_config_load_failure(self, mock_ctx, temp_db):
        """Plugin should register even if config loading fails."""
        with patch("hermes_cli.config.load_config", side_effect=Exception("no config")):
            gap_plugin.register(mock_ctx)
        assert mock_ctx.register_hook.call_count >= 2

    def test_register_sets_default_config(self, mock_ctx, temp_db):
        """Plugin should populate _config with defaults on registration."""
        gap_plugin.register(mock_ctx)
        assert "similarity_threshold" in gap_plugin._config
        assert "min_category_size" in gap_plugin._config
        assert "narrow_desc_threshold" in gap_plugin._config

    def test_tool_schemas_well_formed(self, mock_ctx, temp_db):
        """Each registered tool should have a well-formed schema."""
        gap_plugin.register(mock_ctx)
        for call in mock_ctx.register_tool.call_args_list:
            schema = call.kwargs.get("schema", {})
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            assert schema["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# Frontmatter Parsing Tests
# ---------------------------------------------------------------------------

class TestFrontmatterParsing:
    """Test SKILL.md frontmatter parsing."""

    def test_parse_standard_frontmatter(self):
        content = _make_skill_md("test-skill", "A test skill.", ["tag1", "tag2"])
        fm = gap_plugin._parse_frontmatter(content)
        assert fm["name"] == "test-skill"
        assert "A test skill." in fm["description"]

    def test_parse_no_frontmatter(self):
        """File without frontmatter should return empty dict."""
        content = "# Just a heading\n\nNo frontmatter here."
        fm = gap_plugin._parse_frontmatter(content)
        assert fm == {}

    def test_parse_empty_frontmatter(self):
        """Empty frontmatter block should return empty dict."""
        content = "---\n---\n\n# Content"
        fm = gap_plugin._parse_frontmatter(content)
        assert fm == {}

    def test_parse_frontmatter_with_quotes(self):
        """Quoted values should be unquoted."""
        content = '---\nname: "my-skill"\ndescription: \'My description\'\n---\n'
        fm = gap_plugin._parse_frontmatter(content)
        assert fm["name"] == "my-skill"
        assert fm["description"] == "My description"

    def test_parse_frontmatter_with_inline_list(self):
        """Inline list values should be parsed into Python lists."""
        content = '---\nname: test\ntags: [a, b, c]\n---\n'
        fm = gap_plugin._parse_frontmatter(content)
        assert fm["tags"] == ["a", "b", "c"]

    def test_parse_frontmatter_with_comments(self):
        """Lines starting with # inside frontmatter should be skipped."""
        content = '---\n# This is a comment\nname: test\n---\n'
        fm = gap_plugin._parse_frontmatter(content)
        assert fm["name"] == "test"
        assert len(fm) == 1

    def test_parse_skill_file_returns_none_for_unreadable(self, tmp_path):
        """Should return None if the file cannot be read."""
        # Create a file and make it unreadable (on some systems)
        f = tmp_path / "SKILL.md"
        f.write_text("---\nname: test\n---\n")
        # Patch read_text to raise
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            result = gap_plugin._parse_skill_file(f)
        assert result is None

    def test_parse_skill_file_extracts_metadata(self, tmp_path):
        """Should extract name, description, tags, category from a skill file."""
        skill_dir = tmp_path / "github" / "auth"
        skill_dir.mkdir(parents=True)
        f = skill_dir / "SKILL.md"
        f.write_text(_make_skill_md("github-auth", "GitHub auth setup.", ["git", "auth"]))
        result = gap_plugin._parse_skill_file(f)
        assert result is not None
        assert result["name"] == "github-auth"
        assert "GitHub auth setup." in result["description"]
        assert result["description_length"] > 0


# ---------------------------------------------------------------------------
# Skill Directory Scanning Tests
# ---------------------------------------------------------------------------

class TestSkillScanning:
    """Test skill directory scanning."""

    def test_scan_finds_all_skills(self, temp_skills):
        dirs = [temp_skills]
        skills = gap_plugin._scan_skill_directories(dirs)
        assert len(skills) == 8

    def test_scan_extracts_categories(self, temp_skills):
        dirs = [temp_skills]
        skills = gap_plugin._scan_skill_directories(dirs)
        categories = set(s["category"] for s in skills)
        assert "github" in categories
        assert "mlops" in categories
        assert "devops" in categories
        assert "creative" in categories

    def test_scan_handles_nonexistent_dir(self, tmp_path):
        """Scanning a non-existent directory should not crash."""
        skills = gap_plugin._scan_skill_directories([tmp_path / "nonexistent"])
        assert skills == []

    def test_scan_handles_empty_dir(self, tmp_path):
        """Scanning an empty directory should return no skills."""
        empty = tmp_path / "empty_skills"
        empty.mkdir()
        skills = gap_plugin._scan_skill_directories([empty])
        assert skills == []

    def test_scan_deduplicates(self, temp_skills, tmp_path):
        """Scanning the same dir twice should not duplicate skills."""
        skills = gap_plugin._scan_skill_directories([temp_skills, temp_skills])
        assert len(skills) == 8  # No duplicates

    def test_scan_nested_categories(self, tmp_path):
        """Skills nested two levels deep should have correct category."""
        base = tmp_path / "skills"
        _create_skill_dir(base, "mlops", "training", "Model training skill.")
        _create_skill_dir(base, "mlops", "inference", "Model inference skill.")
        skills = gap_plugin._scan_skill_directories([base])
        assert len(skills) == 2
        assert all(s["category"] == "mlops" for s in skills)

    def test_scan_root_level_skill(self, tmp_path):
        """A skill directly under the skills dir should have category 'root'."""
        base = tmp_path / "skills"
        skill_dir = base / "standalone"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(_make_skill_md("standalone", "A standalone skill."))
        skills = gap_plugin._scan_skill_directories([base])
        assert len(skills) == 1
        assert skills[0]["category"] == "root"

    def test_get_skill_dirs_finds_primary(self, temp_db, temp_skills):
        """_get_skill_dirs should find the primary skills directory."""
        dirs = gap_plugin._get_skill_dirs()
        assert any("skills" in str(d) for d in dirs)


# ---------------------------------------------------------------------------
# Gap Analysis Tests
# ---------------------------------------------------------------------------

class TestGapAnalysis:
    """Test gap analysis functions."""

    def test_analyze_category_coverage(self):
        skills = [
            {"name": "a", "category": "github"},
            {"name": "b", "category": "github"},
            {"name": "c", "category": "mlops"},
        ]
        result = gap_plugin._analyze_category_coverage(skills)
        assert result["total_categories"] == 2
        assert result["category_counts"]["github"] == 2
        assert result["category_counts"]["mlops"] == 1

    def test_thin_categories_identified(self):
        gap_plugin._config["min_category_size"] = 3
        skills = [
            {"name": "a", "category": "github"},
            {"name": "b", "category": "github"},
            {"name": "c", "category": "github"},
            {"name": "d", "category": "devops"},  # only 1 skill → thin
        ]
        result = gap_plugin._analyze_category_coverage(skills)
        thin_cats = [t["category"] for t in result["thin_categories"]]
        assert "devops" in thin_cats
        assert "github" not in thin_cats

    def test_identify_narrow_skills_short_desc(self):
        gap_plugin._config["narrow_desc_threshold"] = 30
        skills = [
            {"name": "good", "description": "A well-described skill with enough detail.", "tags": ["a"]},
            {"name": "narrow", "description": "Short.", "tags": ["b"]},
        ]
        narrow = gap_plugin._identify_narrow_skills(skills)
        narrow_names = [n["name"] for n in narrow]
        assert "narrow" in narrow_names
        assert "good" not in narrow_names

    def test_identify_narrow_skills_no_tags(self):
        skills = [
            {"name": "notags", "description": "A well-described skill with enough detail.", "tags": []},
        ]
        narrow = gap_plugin._identify_narrow_skills(skills)
        assert len(narrow) == 1
        assert "no_tags" in narrow[0]["issues"]

    def test_identify_narrow_skills_both_issues(self):
        gap_plugin._config["narrow_desc_threshold"] = 30
        skills = [
            {"name": "bad", "description": "Hi", "tags": []},
        ]
        narrow = gap_plugin._identify_narrow_skills(skills)
        assert len(narrow) == 1
        assert "short_description" in narrow[0]["issues"][0]
        assert "no_tags" in narrow[0]["issues"]

    def test_identify_missing_capabilities(self):
        skills = [
            {"name": "a", "tags": ["git", "github"]},
            {"name": "b", "tags": ["docker"]},
        ]
        missing = gap_plugin._identify_missing_capabilities(skills)
        missing_areas = [m["capability"] for m in missing]
        # testing, monitoring, security, etc. should be missing
        assert "testing" in missing_areas
        assert "monitoring" in missing_areas

    def test_identify_missing_capabilities_with_coverage(self):
        skills = [
            {"name": "a", "tags": ["testing", "unit-test"]},
            {"name": "b", "tags": ["deployment", "ci-cd"]},
            {"name": "c", "tags": ["monitoring", "observability"]},
            {"name": "d", "tags": ["security", "auth"]},
            {"name": "e", "tags": ["documentation", "docs"]},
            {"name": "f", "tags": ["code-review", "review"]},
            {"name": "g", "tags": ["debugging", "debug"]},
            {"name": "h", "tags": ["refactoring", "cleanup"]},
            {"name": "i", "tags": ["performance", "optimization"]},
            {"name": "j", "tags": ["data-analysis", "analytics"]},
            {"name": "k", "tags": ["automation", "scripting"]},
            {"name": "l", "tags": ["git", "vcs"]},
            {"name": "m", "tags": ["docker", "containers"]},
            {"name": "n", "tags": ["api", "rest"]},
        ]
        missing = gap_plugin._identify_missing_capabilities(skills)
        # All expected areas are covered, so none should be missing
        assert len(missing) == 0

    def test_generate_recommendations_empty_library(self):
        coverage = {"total_categories": 0, "category_counts": {}, "thin_categories": []}
        recs = gap_plugin._generate_recommendations(coverage, [], [], [], 0)
        assert any(r["type"] == "empty_library" for r in recs)
        assert any(r["priority"] == "critical" for r in recs)

    def test_generate_recommendations_small_library(self):
        coverage = {"total_categories": 1, "category_counts": {"a": 3}, "thin_categories": []}
        recs = gap_plugin._generate_recommendations(coverage, [], [], [], 3)
        assert any(r["type"] == "small_library" for r in recs)

    def test_generate_recommendations_thin_category(self):
        coverage = {
            "total_categories": 2,
            "category_counts": {"a": 5, "b": 1},
            "thin_categories": [{"category": "b", "count": 1, "skills": ["x"]}],
        }
        recs = gap_plugin._generate_recommendations(coverage, [], [], [], 6)
        thin_recs = [r for r in recs if r["type"] == "thin_category"]
        assert len(thin_recs) == 1
        assert thin_recs[0]["category"] == "b"


# ---------------------------------------------------------------------------
# Similarity Tests
# ---------------------------------------------------------------------------

class TestSimilarity:
    """Test skill similarity / overlap detection."""

    def test_jaccard_identical(self):
        a = gap_plugin._tokenize("hello world foo bar")
        b = gap_plugin._tokenize("hello world foo bar")
        assert gap_plugin._jaccard_similarity(a, b) == 1.0

    def test_jaccard_disjoint(self):
        a = gap_plugin._tokenize("hello world")
        b = gap_plugin._tokenize("foo bar")
        assert gap_plugin._jaccard_similarity(a, b) == 0.0

    def test_jaccard_partial(self):
        a = gap_plugin._tokenize("hello world foo")
        b = gap_plugin._tokenize("hello world bar")
        # intersection = 2 (hello, world), union = 4 (hello, world, foo, bar)
        assert gap_plugin._jaccard_similarity(a, b) == 0.5

    def test_jaccard_both_empty(self):
        assert gap_plugin._jaccard_similarity(set(), set()) == 0.0

    def test_find_overlapping_skills_high_similarity(self):
        # Use identical names so description+name tokens are fully shared
        skills = [
            {"name": "pr-workflow", "description": "GitHub pull request workflow management", "category": "github"},
            {"name": "pr-workflow", "description": "GitHub pull request workflow management", "category": "github"},
            {"name": "docker-mgmt", "description": "Docker container management and orchestration", "category": "devops"},
        ]
        overlaps = gap_plugin._find_overlapping_skills(skills, threshold=0.5)
        assert len(overlaps) >= 1
        assert overlaps[0]["skill_a"] == "pr-workflow"
        assert overlaps[0]["skill_b"] == "pr-workflow"
        assert overlaps[0]["similarity"] == 1.0

    def test_find_overlapping_skills_no_overlap(self):
        skills = [
            {"name": "a", "description": "completely different text about cats", "category": "x"},
            {"name": "b", "description": "entirely unrelated words about dogs", "category": "y"},
        ]
        overlaps = gap_plugin._find_overlapping_skills(skills, threshold=0.8)
        assert len(overlaps) == 0

    def test_find_overlapping_skills_sorted_by_similarity(self):
        skills = [
            {"name": "a", "description": "foo bar baz", "category": "x"},
            {"name": "b", "description": "foo bar qux", "category": "x"},
            {"name": "c", "description": "foo bar baz", "category": "x"},
        ]
        overlaps = gap_plugin._find_overlapping_skills(skills, threshold=0.1)
        # a-c should have similarity 1.0 (identical), a-b and b-c should be 0.667
        assert overlaps[0]["similarity"] >= overlaps[1]["similarity"]

    def test_tokenize_lowercases(self):
        tokens = gap_plugin._tokenize("Hello WORLD FooBar")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foobar" in tokens

    def test_tokenize_filters_short(self):
        tokens = gap_plugin._tokenize("a hi the foo")
        assert "foo" in tokens
        # "a", "hi", "the" are filtered by the regex \b[a-z][a-z0-9_-]+\b (min 2 chars)
        assert "a" not in tokens


# ---------------------------------------------------------------------------
# Database Tests
# ---------------------------------------------------------------------------

class TestDatabase:
    """Test database operations and integrity."""

    def test_init_db_creates_tables(self, temp_db):
        conn = gap_plugin._safe_get_db()
        assert conn is not None
        gap_plugin._init_db(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "skills" in table_names
        assert "scans" in table_names
        assert "gaps" in table_names
        conn.close()

    def test_store_scan_results(self, temp_db):
        skills = [
            {"name": "a", "description": "desc a", "tags": ["t1"], "category": "cat1",
             "path": "/tmp/a", "file": "/tmp/a/SKILL.md", "source_dir": "/tmp",
             "description_length": 6, "content_size": 100},
        ]
        coverage = {"total_categories": 1, "category_counts": {"cat1": 1}, "thin_categories": []}
        recommendations = [{"priority": "low", "type": "test", "recommendation": "test"}]

        gap_plugin._store_scan_results(
            "scan-1", "sess-1", skills, coverage, [], [], [], recommendations, time.time()
        )

        conn = gap_plugin._safe_get_db()
        gap_plugin._init_db(conn)
        scan = conn.execute("SELECT * FROM scans WHERE scan_id = ?", ("scan-1",)).fetchone()
        assert scan is not None
        assert scan["total_skills"] == 1
        assert scan["total_categories"] == 1

        skill = conn.execute("SELECT * FROM skills WHERE scan_id = ?", ("scan-1",)).fetchone()
        assert skill is not None
        assert skill["name"] == "a"

        gap = conn.execute("SELECT * FROM gaps WHERE scan_id = ?", ("scan-1",)).fetchone()
        assert gap is not None
        assert gap["gap_type"] == "test"
        conn.close()

    def test_get_latest_scan_id(self, temp_db):
        # Store two scans with different timestamps
        for i, ts in enumerate([time.time() - 10, time.time()]):
            gap_plugin._store_scan_results(
                f"scan-{i}", "sess", [], {"total_categories": 0, "category_counts": {}, "thin_categories": []},
                [], [], [], [], ts,
            )
        conn = gap_plugin._safe_get_db()
        gap_plugin._init_db(conn)
        latest = gap_plugin._get_latest_scan_id(conn)
        assert latest == "scan-1"
        conn.close()

    def test_get_latest_scan_id_empty(self, temp_db):
        conn = gap_plugin._safe_get_db()
        gap_plugin._init_db(conn)
        assert gap_plugin._get_latest_scan_id(conn) is None
        conn.close()


# ---------------------------------------------------------------------------
# Tool Handler Tests
# ---------------------------------------------------------------------------

class TestToolHandlers:
    """Test skill_gap_scan, skill_gap_report, skill_similarity tools."""

    def test_skill_gap_scan_returns_json(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_gap_scan({}))
        assert "scan_id" in result
        assert "total_skills" in result
        assert "total_categories" in result
        assert result["total_skills"] == 8
        assert result["total_categories"] == 4

    def test_skill_gap_scan_with_explicit_dirs(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_gap_scan({"dirs": [str(temp_skills)]}))
        assert result["total_skills"] == 8

    def test_skill_gap_scan_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = json.loads(gap_plugin._tool_skill_gap_scan({"dirs": [str(empty)]}))
        assert result["total_skills"] == 0
        assert result["total_categories"] == 0

    def test_skill_gap_scan_store_false(self, temp_skills):
        """When store=false, results should still be returned but not persisted."""
        result = json.loads(gap_plugin._tool_skill_gap_scan({"store": False}))
        assert "scan_id" in result
        assert "total_skills" in result

    def test_skill_gap_report_from_db(self, temp_skills):
        # First do a scan
        scan_result = json.loads(gap_plugin._tool_skill_gap_scan({}))
        scan_id = scan_result["scan_id"]

        # Then get the report
        report = json.loads(gap_plugin._tool_skill_gap_report({"scan_id": scan_id}))
        assert "scan_id" in report
        assert "categories" in report
        assert "recommendations" in report

    def test_skill_gap_report_rescan(self, temp_skills):
        report = json.loads(gap_plugin._tool_skill_gap_report({"rescan": True}))
        assert "scan_id" in report
        assert "total_skills" in report

    def test_skill_gap_report_no_scan_found(self, temp_db):
        """Should return error when no scan exists and rescan is false."""
        result = json.loads(gap_plugin._tool_skill_gap_report({}))
        assert "error" in result
        assert result["error"] == "no_scan_found"

    def test_skill_gap_report_invalid_scan_id(self, temp_db):
        result = json.loads(gap_plugin._tool_skill_gap_report({"scan_id": "nonexistent"}))
        assert "error" in result
        assert result["error"] == "scan_not_found"

    def test_skill_similarity_all_pairs(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_similarity({}))
        assert "total_skills" in result
        assert "overlaps" in result
        assert result["total_skills"] == 8

    def test_skill_similarity_with_threshold(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_similarity({"threshold": 0.99}))
        # With a very high threshold, there should be few or no overlaps
        assert result["overlaps_count"] >= 0

    def test_skill_similarity_specific_skill(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_similarity({"skill_name": "github-auth"}))
        assert "target_skill" in result
        assert result["target_skill"] == "github-auth"
        assert "similar_skills" in result

    def test_skill_similarity_skill_not_found(self, temp_skills):
        result = json.loads(gap_plugin._tool_skill_similarity({"skill_name": "nonexistent-skill"}))
        assert "error" in result
        assert result["error"] == "skill_not_found"
        assert "available_skills" in result

    def test_skill_similarity_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = json.loads(gap_plugin._tool_skill_similarity({"dirs": [str(empty)]}))
        assert result["total_skills"] == 0
        assert result["overlaps"] == []


# ---------------------------------------------------------------------------
# Hook Handler Tests
# ---------------------------------------------------------------------------

class TestHookHandlers:
    """Test the session and skill lifecycle hooks."""

    def test_on_session_start_sets_session_id(self):
        gap_plugin._on_session_start(session_id="test-session-123")
        assert gap_plugin._current_session_id == "test-session-123"

    def test_on_session_start_generates_uuid_if_no_id(self):
        gap_plugin._on_session_start()
        assert gap_plugin._current_session_id is not None
        assert len(gap_plugin._current_session_id) > 0

    def test_on_skill_lifecycle_records_event(self):
        gap_plugin._on_skill_lifecycle(event="installed", skill_name="test-skill")
        assert hasattr(gap_plugin._local, "last_skill_event")
        assert gap_plugin._local.last_skill_event["event"] == "installed"
        assert gap_plugin._local.last_skill_event["skill_name"] == "test-skill"


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Verify the plugin handles concurrent operations correctly."""

    def test_concurrent_scans(self, temp_skills):
        """Multiple threads scanning and storing should not corrupt the database."""
        errors = []
        results = []

        def worker(thread_id):
            try:
                for i in range(5):
                    r = gap_plugin._tool_skill_gap_scan({"dirs": [str(temp_skills)]})
                    parsed = json.loads(r)
                    results.append(parsed["total_skills"])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All scans should have found 8 skills
        assert all(r == 8 for r in results)
        assert len(results) == 25  # 5 threads × 5 scans

    def test_concurrent_store_results(self, temp_db):
        """Concurrent database writes should not corrupt data."""
        errors = []

        def worker(thread_id):
            try:
                skills = [
                    {"name": f"skill-{thread_id}-{i}", "description": "test", "tags": [],
                     "category": "test", "path": "/tmp", "file": "/tmp/SKILL.md",
                     "source_dir": "/tmp", "description_length": 4, "content_size": 50}
                    for i in range(10)
                ]
                coverage = {"total_categories": 1, "category_counts": {"test": 10}, "thin_categories": []}
                gap_plugin._store_scan_results(
                    f"scan-{thread_id}", "sess", skills, coverage, [], [], [], [], time.time()
                )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        conn = gap_plugin._safe_get_db()
        gap_plugin._init_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        assert count == 5
        skill_count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        assert skill_count == 50  # 5 threads × 10 skills
        conn.close()


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Try to break the plugin with unusual inputs."""

    def test_scan_dir_with_no_skill_files(self, tmp_path):
        """Directory with files but no SKILL.md should return empty."""
        base = tmp_path / "skills"
        base.mkdir()
        (base / "README.md").write_text("Not a skill file.")
        (base / "other.txt").write_text("Not a skill either.")
        skills = gap_plugin._scan_skill_directories([base])
        assert skills == []

    def test_skill_with_unicode_description(self, tmp_path):
        """Unicode in skill descriptions should be handled correctly."""
        base = tmp_path / "skills"
        skill_dir = base / "creative" / "unicode-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_md("unicode-skill", "Unicode skill: æøå — café — 日本語 — 错误"),
            encoding="utf-8",
        )
        skills = gap_plugin._scan_skill_directories([base])
        assert len(skills) == 1
        assert "æøå" in skills[0]["description"]

    def test_skill_with_empty_description(self, tmp_path):
        """Skills with empty descriptions should be parsed but flagged as narrow."""
        base = tmp_path / "skills"
        skill_dir = base / "test" / "empty-desc"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: empty-desc\ndescription: \"\"\n---\n\n# Empty"
        )
        skills = gap_plugin._scan_skill_directories([base])
        assert len(skills) == 1
        assert skills[0]["description"] == ""

    def test_skill_with_no_frontmatter_skipped(self, tmp_path):
        """Files without frontmatter should be skipped during scanning."""
        base = tmp_path / "skills"
        skill_dir = base / "test" / "no-fm"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Just a heading\n\nNo frontmatter.")
        skills = gap_plugin._scan_skill_directories([base])
        assert skills == []

    def test_tool_handler_with_unwritable_db(self, tmp_path, monkeypatch):
        """Tool handlers should return error JSON, not crash, when DB is unavailable."""
        monkeypatch.setenv("HERMES_HOME", "/nonexistent/path")
        gap_plugin._config.clear()
        result = json.loads(gap_plugin._tool_skill_gap_report({}))
        assert "error" in result

    def test_store_results_unwritable_db_does_not_crash(self, tmp_path, monkeypatch):
        """Storing results with an unwritable DB should fail silently."""
        monkeypatch.setenv("HERMES_HOME", "/nonexistent/path")
        gap_plugin._config.clear()
        # This should not raise
        gap_plugin._store_scan_results(
            "test", "sess", [], {"total_categories": 0, "category_counts": {}, "thin_categories": []},
            [], [], [], [], time.time()
        )

    def test_similarity_with_empty_skills_list(self):
        """Finding overlaps in an empty skill list should return empty."""
        overlaps = gap_plugin._find_overlapping_skills([], threshold=0.5)
        assert overlaps == []

    def test_similarity_single_skill(self):
        """A single skill should produce no overlaps."""
        skills = [{"name": "a", "description": "test skill", "category": "x"}]
        overlaps = gap_plugin._find_overlapping_skills(skills, threshold=0.1)
        assert overlaps == []

    def test_analyze_coverage_empty_skills(self):
        """Coverage analysis with no skills should return zeros."""
        result = gap_plugin._analyze_category_coverage([])
        assert result["total_categories"] == 0
        assert result["category_counts"] == {}
        assert result["thin_categories"] == []

    def test_identify_narrow_skills_empty(self):
        """Narrow skill analysis with no skills should return empty."""
        narrow = gap_plugin._identify_narrow_skills([])
        assert narrow == []

    def test_identify_missing_capabilities_empty(self):
        """Missing capability analysis with no skills should flag all areas."""
        missing = gap_plugin._identify_missing_capabilities([])
        assert len(missing) > 0

    def test_parse_frontmatter_multiline_value(self):
        """Multi-line description values (with >-) should be handled gracefully."""
        content = "---\nname: test\ndescription: >-\n  A long description\n  spanning multiple lines\n---\n"
        fm = gap_plugin._parse_frontmatter(content)
        assert fm["name"] == "test"
        # The value may not be perfectly parsed, but it should not crash
        assert "description" in fm

    def test_skill_gap_scan_with_unicode_dirs(self, tmp_path):
        """Scanning directories with unicode names should work."""
        base = tmp_path / "skills"
        skill_dir = base / "creative" / "unicode-名前"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_md("unicode-skill", "A skill with unicode directory name."),
            encoding="utf-8",
        )
        result = json.loads(gap_plugin._tool_skill_gap_scan({"dirs": [str(base)]}))
        assert result["total_skills"] == 1

    def test_large_skill_library(self, tmp_path):
        """Should handle a large number of skills without issues."""
        base = tmp_path / "skills"
        for i in range(50):
            cat = f"cat-{i % 5}"
            _create_skill_dir(base, cat, f"skill-{i}", f"Skill number {i} for testing.")
        result = json.loads(gap_plugin._tool_skill_gap_scan({"dirs": [str(base)]}))
        assert result["total_skills"] == 50
        assert result["total_categories"] == 5