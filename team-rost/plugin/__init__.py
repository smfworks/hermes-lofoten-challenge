"""context-bridge — preserve context across Hermes session resets.

Inspired by Røst's seabird cliffs in the Lofoten archipelago — Norway's
largest seabird colony, where hundreds of species adapt to the harsh
Arctic environment by preserving and transmitting knowledge across
generations.  Just as puffins return to the same nesting ledge season
after season, carrying the memory of successful foraging grounds,
context-bridge ensures an agent's hard-won findings survive session
resets and are available when the next session begins.

Hooks:
  - on_session_end   → save a context snapshot before the session dies
  - on_session_start → detect a prior snapshot and surface it to the agent
  - on_session_reset → save current context before the reset wipes it

Slash command:
  /context-bridge              → show last snapshot for this profile
  /context-bridge list         → list all available snapshots
  /context-bridge restore [id] → show details of a specific snapshot
  /context-bridge clear [N]    → keep only N most recent per profile
  /context-bridge help         → show help text

Storage:
  ~/.hermes/context-bridge/
    snapshots/   → JSON files named <profile>_<session_id>_<timestamp>.json
    bridge.log   → append-only event log

Safety:
  - Atomic writes (.tmp → os.replace)
  - Thread-safe via threading.Lock()
  - Snapshots capped at 50 entries and 10 KB
  - Auto-cleans old snapshots (keeps last 10 per profile)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

_MAX_ENTRIES = 50          # max tool-call / finding entries per snapshot
_MAX_SNAPSHOT_BYTES = 10_000  # hard cap on serialized snapshot size
_DEFAULT_KEEP = 10         # default snapshots to retain per profile on cleanup
_LOCK = threading.Lock()   # serialises all file I/O for thread safety


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _hermes_home() -> Path:
    """Return the Hermes home directory from HERMES_HOME env var.

    Falls back to ``~/.hermes`` if the env var is not set.
    """
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val).expanduser().resolve()
    return Path.home() / ".hermes"


def _base_dir() -> Path:
    """Root directory for all context-bridge data."""
    return _hermes_home() / "context-bridge"


def _snapshots_dir() -> Path:
    """Directory where snapshot JSON files are stored."""
    return _base_dir() / "snapshots"


def _log_file() -> Path:
    """Path to the append-only bridge.log."""
    return _base_dir() / "bridge.log"


def _profile_name() -> str:
    """Extract the profile name from HERMES_HOME.

    HERMES_HOME is typically ``~/.hermes/profiles/<profile>``.
    Returns ``"default"`` as a fallback.
    """
    home = _hermes_home()
    parts = home.parts
    # Look for "profiles" in the path and take the next segment
    for i, part in enumerate(parts):
        if part == "profiles" and i + 1 < len(parts):
            return parts[i + 1]
    # If HERMES_HOME is just ~/.hermes, use "default"
    return "default"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(message: str) -> None:
    """Append a timestamped line to bridge.log.

    Creates parent directories if needed.  Never raises — logging is
    best-effort.
    """
    try:
        log_path = _log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {message}\n")
    except Exception:
        pass  # logging must never disrupt the agent


# ---------------------------------------------------------------------------
# Atomic file I/O
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write *data* as JSON to *path* atomically.

    Writes to a ``.tmp`` sibling first, then ``os.replace`` for atomic
    swap.  Raises on failure so callers can decide how to handle.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    os.replace(str(tmp), str(path))  # atomic on POSIX


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file, returning None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        return json.loads(content)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

def _build_snapshot(
    session_id: str,
    reason: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    key_findings: Optional[List[str]] = None,
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a context snapshot dict, enforcing size limits.

    Parameters
    ----------
    session_id : str
        The Hermes session identifier (may be empty string).
    reason : str
        Why the snapshot was taken: ``"session_end"``, ``"session_reset"``,
        or ``"session_start"``.
    tool_calls : list of dict, optional
        Recent tool call records (name, args summary, result summary).
    key_findings : list of str, optional
        Important discoveries or decisions from the session.
    task_state : dict, optional
        Current task state (what was being worked on, progress, next steps).

    Returns
    -------
    dict
        A snapshot dictionary ready for JSON serialisation.
    """
    now = datetime.now(timezone.utc)

    # Enforce entry limits
    tool_calls = (tool_calls or [])[:_MAX_ENTRIES]
    key_findings = (key_findings or [])[:_MAX_ENTRIES]

    snapshot = {
        "session_id": session_id or "unknown",
        "profile": _profile_name(),
        "reason": reason,
        "timestamp": now.isoformat(),
        "tool_calls": tool_calls,
        "key_findings": key_findings,
        "task_state": task_state or {},
        "version": "1.0.0",
    }

    # Enforce byte limit by trimming tool_calls from the front (keep most recent)
    while len(json.dumps(snapshot, default=str)) > _MAX_SNAPSHOT_BYTES:
        if snapshot["tool_calls"]:
            snapshot["tool_calls"].pop(0)
        elif snapshot["key_findings"]:
            snapshot["key_findings"].pop(0)
        else:
            break  # can't trim further

    return snapshot


def _save_snapshot(snapshot: Dict[str, Any]) -> Optional[str]:
    """Persist a snapshot to disk and return the filename, or None on error.

    Filename format: ``<profile>_<session_id>_<timestamp>.json``
    Where timestamp uses a filesystem-safe format.
    """
    with _LOCK:
        try:
            ts_safe = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            profile = snapshot.get("profile", "default")
            sid = snapshot.get("session_id", "unknown")
            # Sanitise for filesystem safety
            sid_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)
            filename = f"{profile}_{sid_safe}_{ts_safe}.json"
            path = _snapshots_dir() / filename

            _atomic_write_json(path, snapshot)

            _log(f"SNAPSHOT_SAVED: {filename} (reason={snapshot.get('reason', '?')})")

            # Auto-clean old snapshots after each save
            _auto_clean(profile)

            return filename
        except Exception as exc:
            _log(f"SNAPSHOT_SAVE_ERROR: {exc}")
            logger.error("context-bridge: failed to save snapshot: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Snapshot discovery and cleanup
# ---------------------------------------------------------------------------

def _list_snapshots(profile: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all snapshots, optionally filtered by profile.

    Returns a list of dicts with ``filename``, ``snapshot`` (parsed or
    None if corrupt), and ``mtime``.  Sorted by mtime descending (newest
    first).
    """
    with _LOCK:
        results: List[Dict[str, Any]] = []
        snap_dir = _snapshots_dir()
        if not snap_dir.exists():
            return results
        for entry in sorted(snap_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if entry.suffix != ".json" or not entry.is_file():
                continue
            if profile:
                # Filename starts with <profile>_
                if not entry.name.startswith(f"{profile}_"):
                    continue
            parsed = _read_json(entry)
            results.append({
                "filename": entry.name,
                "snapshot": parsed,
                "mtime": entry.stat().st_mtime,
            })
        return results


def _auto_clean(profile: str, keep: int = _DEFAULT_KEEP) -> int:
    """Remove old snapshots for *profile*, keeping the *keep* newest.

    Returns the number of files deleted.  Called automatically after each
    save.  Never raises.
    """
    try:
        snap_dir = _snapshots_dir()
        if not snap_dir.exists():
            return 0
        # Collect files for this profile
        profile_files: List[Path] = []
        for entry in snap_dir.iterdir():
            if entry.suffix == ".json" and entry.name.startswith(f"{profile}_"):
                profile_files.append(entry)
        if len(profile_files) <= keep:
            return 0
        # Sort by mtime, oldest first
        profile_files.sort(key=lambda p: p.stat().st_mtime)
        to_delete = profile_files[:-keep] if keep > 0 else profile_files
        deleted = 0
        for f in to_delete:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
        if deleted:
            _log(f"AUTO_CLEAN: removed {deleted} old snapshot(s) for profile '{profile}'")
        return deleted
    except Exception as exc:
        _log(f"AUTO_CLEAN_ERROR: {exc}")
        return 0


def _find_snapshot_by_id(snapshot_id: str) -> Optional[Dict[str, Any]]:
    """Find a snapshot by filename (or partial match).

    Returns the parsed snapshot dict or None if not found / corrupt.
    """
    with _LOCK:
        snap_dir = _snapshots_dir()
        if not snap_dir.exists():
            return None
        # Exact match
        exact = snap_dir / snapshot_id
        if exact.exists() and exact.suffix == ".json":
            return _read_json(exact)
        # Partial match — find a file whose name contains the ID
        if not snapshot_id.endswith(".json"):
            for entry in snap_dir.iterdir():
                if entry.suffix == ".json" and snapshot_id in entry.name:
                    return _read_json(entry)
        return None


# ---------------------------------------------------------------------------
# Hook implementations
# ---------------------------------------------------------------------------

def _on_session_end(
    session_id: str = "",
    completed: bool = True,
    interrupted: bool = False,
    **kwargs: Any,
) -> None:
    """Save a context snapshot when a session ends.

    Captures any tool-call history or task state passed via kwargs.
    Falls back to a minimal snapshot if no data is available.
    """
    try:
        tool_calls = kwargs.get("tool_calls", [])
        key_findings = kwargs.get("key_findings", [])
        task_state = kwargs.get("task_state", {})

        # If interrupted, note it in task_state
        if interrupted:
            task_state = dict(task_state)
            task_state["interrupted"] = True

        snapshot = _build_snapshot(
            session_id=session_id,
            reason="session_end",
            tool_calls=tool_calls,
            key_findings=key_findings,
            task_state=task_state,
        )
        _save_snapshot(snapshot)
    except Exception as exc:
        _log(f"SESSION_END_ERROR: {exc}")
        logger.error("context-bridge: on_session_end failed: %s", exc)


def _on_session_start(
    session_id: str = "",
    **kwargs: Any,
) -> None:
    """Check for a recent snapshot and log its availability.

    The snapshot is not automatically injected — it is made discoverable
    via the ``/context-bridge`` command.  This hook logs the presence of
    a prior snapshot so the agent can retrieve it if needed.
    """
    try:
        profile = _profile_name()
        snapshots = _list_snapshots(profile)
        if snapshots:
            latest = snapshots[0]
            _log(
                f"SESSION_START: prior snapshot available: "
                f"{latest['filename']} "
                f"(reason={latest['snapshot'].get('reason', '?') if latest['snapshot'] else 'corrupt'})"
            )
        else:
            _log(f"SESSION_START: no prior snapshots for profile '{profile}'")
    except Exception as exc:
        _log(f"SESSION_START_ERROR: {exc}")
        logger.error("context-bridge: on_session_start failed: %s", exc)


def _on_session_reset(
    session_id: str = "",
    **kwargs: Any,
) -> None:
    """Save current context before a session reset wipes it.

    This is the critical hook — resets happen when context windows fill
    or when the user explicitly resets.  Without this hook, all in-flight
    findings would be lost.
    """
    try:
        tool_calls = kwargs.get("tool_calls", [])
        key_findings = kwargs.get("key_findings", [])
        task_state = kwargs.get("task_state", {})
        task_state = dict(task_state)
        task_state["reset_reason"] = kwargs.get("reason", "unknown")

        snapshot = _build_snapshot(
            session_id=session_id,
            reason="session_reset",
            tool_calls=tool_calls,
            key_findings=key_findings,
            task_state=task_state,
        )
        _save_snapshot(snapshot)
    except Exception as exc:
        _log(f"SESSION_RESET_ERROR: {exc}")
        logger.error("context-bridge: on_session_reset failed: %s", exc)


# ---------------------------------------------------------------------------
# Slash command
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
/context-bridge — preserve and restore context across session resets

Subcommands:
  (none)              Show the most recent snapshot for this profile
  list                List all available snapshots
  restore [id]        Show details of a specific snapshot (by filename or partial match)
  clear [N]           Keep only the N most recent snapshots per profile (default 10)
  help                Show this help message

Snapshots are saved automatically on session_end and session_reset.
Use 'restore' to view a prior session's tool calls, findings, and task state.

The Lofoten Connection:
  Røst's seabirds return to the same nesting ledges each season, carrying
  the memory of successful foraging grounds.  context-bridge does the same
  for your agent — preserving hard-won findings across session boundaries
  so the next session can pick up where the last one left off.
"""


def _fmt_snapshot_brief(snap: Optional[Dict[str, Any]], filename: str) -> str:
    """Format a one-line summary of a snapshot for list output."""
    if not snap:
        return f"  {filename}  [CORRUPT — unreadable]"
    ts = snap.get("timestamp", "?")
    reason = snap.get("reason", "?")
    sid = snap.get("session_id", "?")
    n_tools = len(snap.get("tool_calls", []))
    n_findings = len(snap.get("key_findings", []))
    return (
        f"  {filename}\n"
        f"    timestamp: {ts}  reason: {reason}  session: {sid}\n"
        f"    tool_calls: {n_tools}  findings: {n_findings}"
    )


def _fmt_snapshot_detail(snap: Optional[Dict[str, Any]], filename: str) -> str:
    """Format a full snapshot for restore output."""
    if not snap:
        return f"Snapshot '{filename}' is corrupt or unreadable."

    lines = [
        f"╔══ context-bridge snapshot ══╗",
        f"  File:      {filename}",
        f"  Session:   {snap.get('session_id', '?')}",
        f"  Profile:   {snap.get('profile', '?')}",
        f"  Reason:    {snap.get('reason', '?')}",
        f"  Timestamp: {snap.get('timestamp', '?')}",
        f"  Version:   {snap.get('version', '?')}",
        "",
    ]

    # Task state
    task_state = snap.get("task_state", {})
    if task_state:
        lines.append("── Task State ──")
        for k, v in task_state.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    # Key findings
    findings = snap.get("key_findings", [])
    if findings:
        lines.append("── Key Findings ──")
        for i, f in enumerate(findings, 1):
            lines.append(f"  {i}. {f}")
        lines.append("")

    # Tool calls
    tool_calls = snap.get("tool_calls", [])
    if tool_calls:
        lines.append("── Recent Tool Calls ──")
        for i, tc in enumerate(tool_calls, 1):
            name = tc.get("name", tc.get("tool", "?"))
            lines.append(f"  {i}. {name}")
            if isinstance(tc.get("args"), dict):
                args_str = json.dumps(tc["args"], default=str)
                if len(args_str) > 200:
                    args_str = args_str[:200] + "…"
                lines.append(f"     args: {args_str}")
            if tc.get("result"):
                result_str = str(tc["result"])
                if len(result_str) > 200:
                    result_str = result_str[:200] + "…"
                lines.append(f"     result: {result_str}")
        lines.append("")

    if not findings and not tool_calls and not task_state:
        lines.append("  (snapshot is empty — no data was captured)")

    lines.append(f"╚══════════════════════════════╝")
    return "\n".join(lines)


def _handle_slash(raw_args: str) -> Optional[str]:
    """Handle the /context-bridge slash command.

    Parses *raw_args* and dispatches to the appropriate subcommand.
    """
    try:
        argv = raw_args.strip().split()

        # No subcommand → show latest snapshot
        if not argv:
            profile = _profile_name()
            snapshots = _list_snapshots(profile)
            if not snapshots:
                return (
                    f"[context-bridge] No snapshots found for profile '{profile}'.\n"
                    f"Snapshots are saved automatically on session_end and session_reset."
                )
            latest = snapshots[0]
            return _fmt_snapshot_detail(latest["snapshot"], latest["filename"])

        sub = argv[0]

        # help
        if sub in ("help", "-h", "--help"):
            return _HELP_TEXT

        # list
        if sub == "list":
            profile = _profile_name()
            snapshots = _list_snapshots(profile)
            if not snapshots:
                return f"[context-bridge] No snapshots found for profile '{profile}'."
            lines = [f"[context-bridge] {len(snapshots)} snapshot(s) for profile '{profile}':"]
            for s in snapshots:
                lines.append(_fmt_snapshot_brief(s["snapshot"], s["filename"]))
            return "\n".join(lines)

        # restore [id]
        if sub == "restore":
            if len(argv) < 2:
                # No ID given → show latest
                profile = _profile_name()
                snapshots = _list_snapshots(profile)
                if not snapshots:
                    return f"[context-bridge] No snapshots to restore."
                latest = snapshots[0]
                return _fmt_snapshot_detail(latest["snapshot"], latest["filename"])
            snap_id = argv[1]
            snap = _find_snapshot_by_id(snap_id)
            if not snap:
                return f"[context-bridge] No snapshot found matching '{snap_id}'."
            # Find the filename for display
            with _LOCK:
                snap_dir = _snapshots_dir()
                filename = snap_id
                if not (snap_dir / snap_id).exists():
                    for entry in snap_dir.iterdir():
                        if entry.suffix == ".json" and snap_id in entry.name:
                            filename = entry.name
                            break
            return _fmt_snapshot_detail(snap, filename)

        # clear [N]
        if sub == "clear":
            keep = _DEFAULT_KEEP
            if len(argv) >= 2:
                try:
                    keep = int(argv[1])
                    if keep < 0:
                        return "[context-bridge] N must be >= 0."
                except ValueError:
                    return f"[context-bridge] Invalid number: '{argv[1]}'."
            profile = _profile_name()
            with _LOCK:
                deleted = _auto_clean(profile, keep=keep)
            if deleted:
                return f"[context-bridge] Cleared {deleted} old snapshot(s), kept {keep} for profile '{profile}'."
            return f"[context-bridge] Nothing to clear — {keep} or fewer snapshots exist for profile '{profile}'."

        return f"Unknown subcommand: {sub}\n\n{_HELP_TEXT}"

    except Exception as exc:
        _log(f"SLASH_CMD_ERROR: {exc}")
        return f"[context-bridge] Error: {exc}"


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the context-bridge plugin with the Hermes plugin system.

    Wires three hooks and one slash command:

    - ``on_session_end``   → save a context snapshot before the session dies
    - ``on_session_start`` → detect a prior snapshot and log its availability
    - ``on_session_reset`` → save current context before the reset wipes it
    - ``/context-bridge``  → manual listing, restoration, and cleanup

    The plugin is entirely self-contained — no external dependencies beyond
    the Python standard library.  All file I/O is atomic and thread-safe.
    """
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_reset", _on_session_reset)
    ctx.register_command(
        "context-bridge",
        handler=_handle_slash,
        description="Preserve and restore context across session resets.",
    )
    _log("PLUGIN_REGISTERED: context-bridge v1.0.0")