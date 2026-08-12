"""
Tests for Skill Gap Analyzer Plugin
=====================================

Oppositional test suite — verifies plugin registration, tool handlers,
edge cases, and error handling.
"""

import json
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the plugin
plugin_path = str(Path(__file__).parent)
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

import __init__ as gap_plugin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    """Point the plugin at a temporary environment."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    gap_plugin._config = {}
    yield tmp_path


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.register_hook = MagicMock()
    ctx.register_tool = MagicMock()
    ctx.manifest = MagicMock()
    ctx.manifest.name = "skill-gap-analyzer"
    ctx.manifest.key = "skill-gap-analyzer"
    return ctx


@pytest.fixture
def temp_skill_dir(tmp_path):
    """Create a temporary skill directory structure for testing."""
    skills_dir = tmp_path / "skills"
    
    # Create a few test skills
    for category, skill_name, desc in [
        ("devops", "docker-mgmt", "Manage Docker containers"),
        ("devops", "k8s-deploy", "Deploy to Kubernetes"),
        ("research", "paper-search", "Search academic papers"),
        ("creative", "ascii-art", "Generate ASCII art"),
    ]:
        skill_path = skills_dir / category / skill_name
        skill_path.mkdir(parents=True)
        (skill_path / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: {desc}\n---\n# {skill_name}\n\n{desc}\n"
        )
    
    return skills_dir


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------

class TestPluginRegistration:
    def test_register_creates_hooks(self, mock_ctx, temp_env):
        gap_plugin.register(mock_ctx)
        hook_names = [call.args[0] for call in mock_ctx.register_hook.call_args_list]
        assert "on_session_start" in hook_names
        assert "on_skill_lifecycle" in hook_names

    def test_register_creates_tools(self, mock_ctx, temp_env):
        gap_plugin.register(mock_ctx)
        tool_names = [call.kwargs.get("name") for call in mock_ctx.register_tool.call_args_list]
        assert "skill_gap_scan" in tool_names
        assert "skill_gap_report" in tool_names
        assert "skill_similarity" in tool_names

    def test_register_handles_config_failure(self, mock_ctx, temp_env):
        with patch("hermes_cli.config.load_config", side_effect=Exception("no config")):
            gap_plugin.register(mock_ctx)
        assert mock_ctx.register_hook.call_count >= 2


# ---------------------------------------------------------------------------
# Skill Scanning Tests
# ---------------------------------------------------------------------------

class TestSkillScanning:
    def test_scan_finds_skills(self, temp_env, temp_skill_dir):
        """Scan should find all SKILL.md files in the skill directory."""
        with patch.object(gap_plugin, '_get_skill_dirs', return_value=[temp_skill_dir]):
            result = json.loads(gap_plugin._tool_skill_gap_scan({}))
            assert result["total_skills"] >= 4
            assert "devops" in result.get("category_counts", {})

    def test_scan_empty_directory(self, temp_env, tmp_path):
        """Scan should handle empty skill directories gracefully."""
        empty_dir = tmp_path / "empty_skills"
        empty_dir.mkdir()
        with patch.object(gap_plugin, '_get_skill_dirs', return_value=[empty_dir]):
            result = json.loads(gap_plugin._tool_skill_gap_scan({}))
            assert result["total_skills"] == 0

    def test_scan_nonexistent_directory(self, temp_env, tmp_path):
        """Scan should handle nonexistent directories gracefully."""
        with patch.object(gap_plugin, '_get_skill_dirs', return_value=[tmp_path / "nonexistent"]):
            result = json.loads(gap_plugin._tool_skill_gap_scan({}))
            assert "error" in result or result["total_skills"] == 0


# ---------------------------------------------------------------------------
# Tool Handler Edge Cases
# ---------------------------------------------------------------------------

class TestToolHandlerEdgeCases:
    def test_scan_with_no_skills_dir(self, temp_env):
        """Should not crash when skills directory doesn't exist."""
        result = json.loads(gap_plugin._tool_skill_gap_scan({}))
        # Should return valid JSON, not crash
        assert isinstance(result, dict)

    def test_report_generates_valid_json(self, temp_env):
        """Report should always return valid JSON."""
        result = json.loads(gap_plugin._tool_skill_gap_report({}))
        assert isinstance(result, dict)

    def test_similarity_with_no_skills(self, temp_env):
        """Similarity should handle empty skill library."""
        result = json.loads(gap_plugin._tool_skill_similarity({}))
        assert isinstance(result, dict)

    def test_all_tools_return_json_strings(self, temp_env):
        """All tool handlers must return JSON strings (Hermes tool contract)."""
        for tool_fn in [gap_plugin._tool_skill_gap_scan, gap_plugin._tool_skill_gap_report, gap_plugin._tool_skill_similarity]:
            result = tool_fn({})
            assert isinstance(result, str), f"{tool_fn.__name__} must return a string"
            json.loads(result)  # Must be valid JSON