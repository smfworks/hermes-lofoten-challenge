"""
Tests for Tool Telemetry Plugin
================================

Oppositional test suite — tries to break the plugin from multiple angles:
- Database corruption / missing tables
- Thread safety under concurrent calls
- Secret redaction completeness
- Large argument handling
- Retention enforcement
- Error handling when DB is unwritable
- Edge cases: empty args, None values, unicode
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

import __init__ as telemetry_plugin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the plugin at a temporary database."""
    db_path = tmp_path / "telemetry.db"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Reset the module's path cache
    telemetry_plugin._config.clear()
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def mock_ctx():
    """Create a mock PluginContext for testing registration."""
    ctx = MagicMock()
    ctx.register_hook = MagicMock()
    ctx.register_tool = MagicMock()
    ctx.manifest = MagicMock()
    ctx.manifest.name = "tool-telemetry"
    ctx.manifest.key = "tool-telemetry"
    return ctx


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------

class TestPluginRegistration:
    """Verify the plugin registers correctly with Hermes."""

    def test_register_creates_hooks(self, mock_ctx, temp_db):
        """Plugin should register three hooks: pre_tool_call, post_tool_call, on_session_start."""
        telemetry_plugin.register(mock_ctx)
        hook_names = [call.args[0] for call in mock_ctx.register_hook.call_args_list]
        assert "pre_tool_call" in hook_names
        assert "post_tool_call" in hook_names
        assert "on_session_start" in hook_names

    def test_register_creates_tools(self, mock_ctx, temp_db):
        """Plugin should register three tools: telemetry_summary, telemetry_failures, telemetry_export."""
        telemetry_plugin.register(mock_ctx)
        tool_names = [call.kwargs.get("name") for call in mock_ctx.register_tool.call_args_list]
        assert "telemetry_summary" in tool_names
        assert "telemetry_failures" in tool_names
        assert "telemetry_export" in tool_names

    def test_register_initializes_db(self, mock_ctx, temp_db):
        """Database file should be created during registration."""
        telemetry_plugin.register(mock_ctx)
        assert temp_db.exists()

    def test_register_handles_config_load_failure(self, mock_ctx, temp_db):
        """Plugin should register even if config loading fails."""
        pytest.importorskip("hermes_cli")
        with patch("hermes_cli.config.load_config", side_effect=Exception("no config")):
            telemetry_plugin.register(mock_ctx)
        # Should still have registered hooks
        assert mock_ctx.register_hook.call_count >= 3


# ---------------------------------------------------------------------------
# Secret Redaction Tests
# ---------------------------------------------------------------------------

class TestSecretRedaction:
    """Verify that secrets are properly redacted before storage."""

    def test_github_token_redacted(self):
        result = telemetry_plugin._redact_string("ghp_1234567890abcdef", telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_openai_key_redacted(self):
        result = telemetry_plugin._redact_string("sk-proj123abc", telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "sk-proj" not in result
        assert "[REDACTED]" in result

    def test_aws_key_redacted(self):
        result = telemetry_plugin._redact_string("AKIAIOSFODNN7EXAMPLE", telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "AKIA" not in result
        assert "[REDACTED]" in result

    def test_huggingface_token_redacted(self):
        result = telemetry_plugin._redact_string("hf_abc123def456", telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "hf_abc" not in result
        assert "[REDACTED]" in result

    def test_normal_text_not_redacted(self):
        result = telemetry_plugin._redact_string("just normal text", telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert result == "just normal text"

    def test_truncation_works(self):
        long_str = "x" * 1000
        result = telemetry_plugin._redact_string(long_str, [], 100)
        assert len(result) < 120
        assert "[truncated]" in result

    def test_redact_args_handles_dict(self):
        args = {"command": "echo ghp_secret123", "path": "/tmp"}
        result = telemetry_plugin._redact_args(args, telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        parsed = json.loads(result)
        assert "ghp_secret" not in parsed["command"]
        assert "[REDACTED]" in parsed["command"]

    def test_redact_args_handles_nested_dict(self):
        args = {"config": {"api_key": "sk-test123", "url": "https://example.com"}}
        result = telemetry_plugin._redact_args(args, telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "sk-test" not in result
        assert "[REDACTED]" in result

    def test_redact_args_handles_none_values(self):
        args = {"value": None, "other": 42}
        result = telemetry_plugin._redact_args(args, [], 500)
        parsed = json.loads(result)
        assert parsed["value"] == "None"
        assert parsed["other"] == "42"

    def test_redact_args_handles_unicode(self):
        args = {"text": "Lofoten — æøå 日本語"}
        result = telemetry_plugin._redact_args(args, [], 500)
        parsed = json.loads(result)
        assert "Lofoten" in parsed["text"]
        assert "æøå" in parsed["text"]


# ---------------------------------------------------------------------------
# Database Tests
# ---------------------------------------------------------------------------

class TestDatabase:
    """Test database operations and integrity."""

    def test_init_db_creates_tables(self, temp_db):
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "tool_calls" in table_names
        assert "sessions" in table_names
        conn.close()

    def test_record_call_inserts_data(self, temp_db):
        telemetry_plugin._record_call(
            call_id="test-1", session_id="sess-1", profile_name="default",
            tool_name="terminal", toolset="terminal", args_redacted='{"cmd": "ls"}',
            duration_ms=42.5, success=True, error_message=None, timestamp=time.time(),
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        row = conn.execute("SELECT * FROM tool_calls WHERE call_id = ?", ("test-1",)).fetchone()
        assert row is not None
        assert row["tool_name"] == "terminal"
        assert row["success"] == 1
        assert row["duration_ms"] == 42.5
        conn.close()

    def test_record_call_updates_session_stats(self, temp_db):
        ts = time.time()
        telemetry_plugin._record_call(
            call_id="t1", session_id="s1", profile_name="default",
            tool_name="tool_a", toolset="core", args_redacted="{}",
            duration_ms=10, success=True, error_message=None, timestamp=ts,
        )
        telemetry_plugin._record_call(
            call_id="t2", session_id="s1", profile_name="default",
            tool_name="tool_b", toolset="core", args_redacted="{}",
            duration_ms=20, success=False, error_message="oops", timestamp=ts,
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        sess = conn.execute("SELECT * FROM sessions WHERE id = ?", ("s1",)).fetchone()
        assert sess["tool_call_count"] == 2
        assert sess["error_count"] == 1
        conn.close()

    def test_retention_deletes_old_records(self, temp_db):
        old_ts = time.time() - (40 * 86400)  # 40 days ago
        telemetry_plugin._record_call(
            call_id="old", session_id="s1", profile_name="default",
            tool_name="tool", toolset="core", args_redacted="{}",
            duration_ms=10, success=True, error_message=None, timestamp=old_ts,
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        telemetry_plugin._enforce_retention(conn, 30)
        row = conn.execute("SELECT * FROM tool_calls WHERE call_id = ?", ("old",)).fetchone()
        assert row is None
        conn.close()

    def test_retention_zero_keeps_everything(self, temp_db):
        old_ts = time.time() - (365 * 86400)  # 1 year ago
        # Set retention to 0 BEFORE inserting so the record isn't auto-deleted
        telemetry_plugin._config["retention_days"] = 0
        telemetry_plugin._record_call(
            call_id="ancient", session_id="s1", profile_name="default",
            tool_name="tool", toolset="core", args_redacted="{}",
            duration_ms=10, success=True, error_message=None, timestamp=old_ts,
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        # Verify the record exists before retention enforcement
        row = conn.execute("SELECT * FROM tool_calls WHERE call_id = ?", ("ancient",)).fetchone()
        assert row is not None, "Record should exist before retention enforcement"
        # With retention_days=0, nothing should be deleted
        telemetry_plugin._enforce_retention(conn, 0)
        row = conn.execute("SELECT * FROM tool_calls WHERE call_id = ?", ("ancient",)).fetchone()
        assert row is not None, "Record should still exist after retention with 0 days"
        conn.close()


# ---------------------------------------------------------------------------
# Hook Handler Tests
# ---------------------------------------------------------------------------

class TestHookHandlers:
    """Test the pre/post tool call hooks."""

    def test_pre_tool_call_sets_thread_local(self, temp_db):
        telemetry_plugin._on_pre_tool_call(
            tool_name="terminal",
            toolset="terminal",
            args={"command": "echo hello"},
        )
        assert hasattr(telemetry_plugin._local, "call_id")
        assert hasattr(telemetry_plugin._local, "start_time")
        assert telemetry_plugin._local.tool_name == "terminal"

    def test_post_tool_call_records_to_db(self, temp_db):
        # Simulate pre call
        telemetry_plugin._on_pre_tool_call(
            tool_name="read_file",
            toolset="file",
            args={"path": "/tmp/test.txt"},
        )
        # Simulate post call
        telemetry_plugin._on_post_tool_call(
            tool_name="read_file",
            toolset="file",
            success=True,
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        row = conn.execute("SELECT * FROM tool_calls ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row["tool_name"] == "read_file"
        assert row["success"] == 1
        conn.close()

    def test_post_tool_call_with_error(self, temp_db):
        telemetry_plugin._on_pre_tool_call(
            tool_name="terminal",
            toolset="terminal",
            args={"command": "false"},
        )
        telemetry_plugin._on_post_tool_call(
            tool_name="terminal",
            toolset="terminal",
            success=False,
            error="Command exited with code 1",
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        row = conn.execute("SELECT * FROM tool_calls ORDER BY id DESC LIMIT 1").fetchone()
        assert row["success"] == 0
        assert "code 1" in row["error_message"]
        conn.close()

    def test_post_tool_call_without_pre_call(self, temp_db):
        """Should handle post_tool_call even if pre_tool_call wasn't called (defensive)."""
        telemetry_plugin._on_post_tool_call(
            tool_name="web_search",
            toolset="web",
            success=True,
        )
        # Should not raise
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        assert count >= 1
        conn.close()


# ---------------------------------------------------------------------------
# Tool Handler Tests
# ---------------------------------------------------------------------------

class TestToolHandlers:
    """Test the telemetry_summary, telemetry_failures, telemetry_export tools."""

    def _seed_data(self, temp_db):
        """Seed test data into the database."""
        now = time.time()
        calls = [
            ("c1", "s1", "terminal", "terminal", 50.0, True, None),
            ("c2", "s1", "read_file", "file", 10.0, True, None),
            ("c3", "s1", "terminal", "terminal", 200.0, False, "command not found"),
            ("c4", "s2", "web_search", "web", 1500.0, True, None),
            ("c5", "s2", "terminal", "terminal", 30.0, False, "timeout"),
            ("c6", "s2", "terminal", "terminal", 30.0, False, "timeout"),
        ]
        for cid, sid, tool, toolset, dur, success, err in calls:
            telemetry_plugin._record_call(
                call_id=cid, session_id=sid, profile_name="test",
                tool_name=tool, toolset=toolset, args_redacted="{}",
                duration_ms=dur, success=success, error_message=err, timestamp=now,
            )

    def test_telemetry_summary_returns_groups(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": 24, "group_by": "tool"}))
        assert result["total_calls"] == 6
        assert len(result["groups"]) >= 3
        # terminal should have 4 calls (1 success, 3 failure)
        terminal = [g for g in result["groups"] if g["grp"] == "terminal"][0]
        assert terminal["total_calls"] == 4
        assert terminal["failures"] == 3

    def test_telemetry_summary_group_by_toolset(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": 24, "group_by": "toolset"}))
        toolsets = [g["grp"] for g in result["groups"]]
        assert "terminal" in toolsets
        assert "file" in toolsets
        assert "web" in toolsets

    def test_telemetry_failures_returns_recent(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_failures({"hours": 24, "limit": 10}))
        assert result["total_failures"] == 3
        assert len(result["recent_failures"]) == 3
        assert len(result["error_clusters"]) >= 2

    def test_telemetry_failures_error_clustering(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_failures({"hours": 24}))
        # "timeout" should appear twice
        timeout_cluster = [c for c in result["error_clusters"] if c["error_message"] == "timeout"]
        assert len(timeout_cluster) == 1
        assert timeout_cluster[0]["occurrence_count"] == 2

    def test_telemetry_export_summary(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_export({"hours": 24, "format": "summary"}))
        assert result["format"] == "summary"
        assert result["total_calls"] == 6
        assert "success_rate" in result
        assert "per_tool" in result

    def test_telemetry_export_full(self, temp_db):
        self._seed_data(temp_db)
        result = json.loads(telemetry_plugin._tool_telemetry_export({"hours": 24, "format": "full"}))
        assert result["format"] == "full"
        assert len(result["records"]) == 6

    def test_telemetry_summary_empty_db(self, temp_db):
        """Should handle an empty database gracefully."""
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": 24}))
        assert result["total_calls"] == 0
        assert result["groups"] == []

    def test_telemetry_failures_empty_db(self, temp_db):
        result = json.loads(telemetry_plugin._tool_telemetry_failures({"hours": 24}))
        assert result["total_failures"] == 0
        assert result["recent_failures"] == []
        assert result["error_clusters"] == []


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Verify the plugin handles concurrent tool calls correctly."""

    def test_concurrent_recording(self, temp_db):
        """Multiple threads recording calls should not corrupt the database."""
        errors = []

        def worker(thread_id):
            try:
                for i in range(20):
                    telemetry_plugin._record_call(
                        call_id=f"t{thread_id}-{i}",
                        session_id=f"sess-{thread_id}",
                        profile_name="test",
                        tool_name=f"tool_{thread_id}",
                        toolset="test",
                        args_redacted="{}",
                        duration_ms=float(i),
                        success=True,
                        error_message=None,
                        timestamp=time.time(),
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        assert count == 100  # 5 threads × 20 calls
        conn.close()


# ---------------------------------------------------------------------------
# Edge Case Tests (Oppositional Assessment)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Try to break the plugin with unusual inputs."""

    def test_empty_args(self):
        result = telemetry_plugin._redact_args({}, [], 500)
        assert json.loads(result) == {}

    def test_none_args(self):
        result = telemetry_plugin._redact_args({"key": None}, [], 500)
        parsed = json.loads(result)
        assert parsed["key"] == "None"

    def test_very_long_args(self):
        args = {"data": "x" * 100000}
        result = telemetry_plugin._redact_args(args, [], 100)
        parsed = json.loads(result)
        assert "[truncated]" in parsed["data"]

    def test_unicode_in_error_message(self, temp_db):
        telemetry_plugin._record_call(
            call_id="unicode-test", session_id="s1", profile_name="default",
            tool_name="tool", toolset="core", args_redacted="{}",
            duration_ms=10, success=False, error_message="错误: æøå — café",
            timestamp=time.time(),
        )
        conn = telemetry_plugin._get_db()
        telemetry_plugin._init_db(conn)
        row = conn.execute("SELECT * FROM tool_calls WHERE call_id = ?", ("unicode-test",)).fetchone()
        assert "错误" in row["error_message"]
        assert "æøå" in row["error_message"]
        conn.close()

    def test_unwritable_db_does_not_crash(self, tmp_path, monkeypatch):
        """If the DB path is unwritable, the plugin should fail silently."""
        # Point to a path that can't be created
        monkeypatch.setenv("HERMES_HOME", "/nonexistent/path/that/does/not/exist")
        telemetry_plugin._config.clear()
        # This should not raise
        telemetry_plugin._record_call(
            call_id="fail-test", session_id="s1", profile_name="default",
            tool_name="tool", toolset="core", args_redacted="{}",
            duration_ms=10, success=True, error_message=None, timestamp=time.time(),
        )
        # No exception means test passes

    def test_tool_handler_with_unwritable_db(self, tmp_path, monkeypatch):
        """Tool handlers should return error JSON, not crash, when DB is unavailable."""
        monkeypatch.setenv("HERMES_HOME", "/nonexistent/path")
        telemetry_plugin._config.clear()
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": 24}))
        assert "error" in result

    def test_negative_hours(self, temp_db):
        """Negative hours should return empty results (cutoff is in the future)."""
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": -1}))
        assert result["total_calls"] == 0

    def test_zero_hours(self, temp_db):
        """Zero hours should return only calls from the current instant."""
        self._seed_zero = True
        # Record a call slightly in the past
        telemetry_plugin._record_call(
            call_id="past", session_id="s1", profile_name="default",
            tool_name="tool", toolset="core", args_redacted="{}",
            duration_ms=10, success=True, error_message=None, timestamp=time.time() - 1,
        )
        result = json.loads(telemetry_plugin._tool_telemetry_summary({"hours": 0}))
        # With 0 hours, cutoff = now, so the call 1 second ago should be excluded
        assert result["total_calls"] == 0

    def test_multiple_secrets_in_one_string(self):
        text = "keys: ghp_abc123 and sk-xyz789 and AKIA_TEST_KEY"
        result = telemetry_plugin._redact_string(text, telemetry_plugin.DEFAULT_REDACT_PATTERNS, 500)
        assert "ghp_" not in result
        assert "sk-xyz" not in result
        assert "AKIA_TEST" not in result
        assert result.count("[REDACTED]") == 3