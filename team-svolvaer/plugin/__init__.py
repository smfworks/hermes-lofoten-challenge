"""cost-watch plugin — per-session and per-profile API cost tracking.

Lofoten Connection
==================

For over 800 years, the stockfish (tørrfisk) trade connected the Lofoten
islands to the world. Fishermen dried cod on wooden racks (hjell),
merchants in Bergen weighed and logged every shipment, and traders
across Europe — from the Hanseatic wharves to the Rialto in Venice —
recorded each exchange in their ledgers. This documentation made the
trade trustworthy: every shipment of value was accounted for, traceable
from the drying racks of Lofoten to the dinner tables of Europe.

This plugin does the same for agent work. Every API request is a
"shipment" of tokens — a measurable exchange of value. By logging each
request with its token counts and estimated cost, we create a ledger
that makes agent spending transparent, auditable, and optimizable.

Just as a merchant in Venice could trace a shipment of stockfish back
to a specific fisherman in Svolvær, a user of this plugin can trace a
session's cost back to individual API requests, models, and profiles.

Hooks
=====

- ``post_api_request`` — after every LLM API call, extract token counts
  and model info, estimate cost, and record it.
- ``on_session_start`` — initialize per-session tracking state.
- ``on_session_end`` — finalize session totals and log a summary.

Data Storage
============

- ``~/.hermes/cost-watch/costs.json`` — shared JSON file with per-profile
  and per-session cost data. Uses atomic writes (.tmp → rename).
- ``~/.hermes/cost-watch/cost.log`` — append-only event log.

Thread Safety
=============

All shared state access is guarded by a ``threading.Lock()``. The
post_api_request hook can fire concurrently on parallel tool calls, so
the lock protects both in-memory state and file writes.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Simple token-to-cost mapping (USD per 1K tokens).
# These are approximate rates for common models. The plugin uses these
# as defaults; real billing may differ.
DEFAULT_COSTS: Dict[str, Dict[str, float]] = {
    # model_name: {"input": per_1k_input, "output": per_1k_output}
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku": {"input": 0.0008, "output": 0.004},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "llama-3.1-70b": {"input": 0.0009, "output": 0.0009},
    "llama-3.1-8b": {"input": 0.0002, "output": 0.0002},
    "mistral-large": {"input": 0.004, "output": 0.012},
    "mistral-small": {"input": 0.0002, "output": 0.0006},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "glm-4": {"input": 0.0001, "output": 0.0001},
    "glm-4.5": {"input": 0.002, "output": 0.008},
    "glm-5.2": {"input": 0.002, "output": 0.008},
}

# Fallback if model not found in DEFAULT_COSTS
FALLBACK_COST = {"input": 0.002, "output": 0.006}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _global_hermes_dir() -> Path:
    """Return the global ~/.hermes directory.

    The plugin stores data at the global level so costs from all profiles
    are in one shared file. We derive this from HERMES_HOME (which points
    to the profile-specific dir like ~/.hermes/profiles/<name>/) by
    walking up, or fall back to ~/.hermes directly.
    """
    hermes_home = os.environ.get("HERMES_HOME", "")
    if hermes_home:
        p = Path(hermes_home).resolve()
        # HERMES_HOME is typically ~/.hermes/profiles/<name>
        # or ~/.hermes/profiles/<name>/profiles/<name> in nested setups.
        # Walk up until we find the .hermes root.
        for parent in [p, *p.parents]:
            if parent.name == ".hermes":
                return parent
        # If we can't find .hermes, use parent of profiles/ dir
        if "profiles" in p.parts:
            idx = p.parts.index("profiles")
            if idx > 0:
                return Path(*p.parts[:idx])
        # Last resort: two levels up from a profiles/<name> path
        return p.parent.parent if p.parent.name == "profiles" else p
    return Path.home() / ".hermes"


def _state_dir() -> Path:
    """Return the cost-watch state directory."""
    return _global_hermes_dir() / "cost-watch"


def _costs_file() -> Path:
    """Return path to the shared costs JSON file."""
    return _state_dir() / "costs.json"


def _log_file() -> Path:
    """Return path to the cost event log."""
    return _state_dir() / "cost.log"


def _current_profile() -> str:
    """Extract the profile name from HERMES_HOME env var.

    HERMES_HOME is typically ``~/.hermes/profiles/<profile_name>``.
    We extract ``<profile_name>`` from the path. Falls back to
    ``"default"`` if HERMES_HOME is not set or the path doesn't match
    the expected pattern.
    """
    hermes_home = os.environ.get("HERMES_HOME", "")
    if hermes_home:
        p = Path(hermes_home)
        # Look for "profiles" in the path; the segment after it is the
        # profile name.
        parts = p.parts
        if "profiles" in parts:
            idx = parts.index("profiles")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return "default"


# ---------------------------------------------------------------------------
# Thread-safe state
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# In-memory cache of the current session's API requests.
# Keyed by session_id → list of request records.
_current_session: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def _get_cost_rate(model: str) -> Dict[str, float]:
    """Look up the per-1K-token cost for a model.

    Tries exact match first, then case-insensitive match, then a
    prefix match (e.g. "gpt-4o-2024-08-06" matches "gpt-4o"). Falls
    back to FALLBACK_COST if nothing matches.
    """
    if not model:
        return FALLBACK_COST

    # Exact match
    if model in DEFAULT_COSTS:
        return DEFAULT_COSTS[model]

    # Case-insensitive match
    model_lower = model.lower()
    for name, rates in DEFAULT_COSTS.items():
        if name.lower() == model_lower:
            return rates

    # Prefix match — handle versioned model names like "gpt-4o-2024-08-06"
    for name, rates in DEFAULT_COSTS.items():
        if model_lower.startswith(name.lower()):
            return rates

    # Reverse prefix — handle "gpt-4o" matching stored "gpt-4o-mini"
    # by checking if stored name starts with the query (less specific)
    for name, rates in DEFAULT_COSTS.items():
        if name.lower().startswith(model_lower):
            return rates

    return FALLBACK_COST


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the USD cost of an API request.

    Uses :func:`_get_cost_rate` to find per-1K-token rates for the
    model, then computes:

        cost = (input_tokens / 1000) * input_rate
             + (output_tokens / 1000) * output_rate

    Always returns a non-negative float.
    """
    rates = _get_cost_rate(model)
    cost = (input_tokens / 1000.0) * rates["input"] + (
        output_tokens / 1000.0
    ) * rates["output"]
    return round(max(cost, 0.0), 6)


# ---------------------------------------------------------------------------
# Atomic file I/O
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write *data* as JSON to *path* atomically.

    Writes to ``path.tmp`` first, then renames to ``path``. This
    ensures the file is never in a partially-written state. Must be
    called under ``_lock``.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")
    os.replace(str(tmp), str(path))


def _load_json(path: Path) -> Dict[str, Any]:
    """Load JSON from *path*, returning an empty dict on any error.

    Handles missing files, corrupted JSON, and permission errors
    gracefully — the plugin must never crash the agent over a bad
    state file.
    """
    try:
        if not path.exists():
            return {}
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("cost-watch: state file %s is not a dict, resetting", path)
            return {}
        return data
    except json.JSONDecodeError:
        logger.warning("cost-watch: corrupted JSON in %s, starting fresh", path)
        return {}
    except Exception as e:
        logger.warning("cost-watch: error loading %s: %s, starting fresh", path, e)
        return {}


def _append_log(message: str) -> None:
    """Append a timestamped line to the cost log file.

    Best-effort: never raises. Must be called under ``_lock``.
    """
    try:
        log_path = _log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(log_path, "a") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception as e:
        logger.debug("cost-watch: failed to write log: %s", e)


# ---------------------------------------------------------------------------
# Data manipulation
# ---------------------------------------------------------------------------


def _ensure_structure(data: Dict[str, Any], profile: str) -> Dict[str, Any]:
    """Ensure *data* has the expected nested structure for *profile*.

    Structure:
    ::
        {
          "profiles": {
            "<profile>": {
              "total_cost": 0.0,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
              "total_requests": 0,
              "sessions": {
                "<session_id>": {
                  "cost": 0.0,
                  "input_tokens": 0,
                  "output_tokens": 0,
                  "requests": 0,
                  "model_breakdown": {},
                  "started_at": "...",
                  "ended_at": "...",
                  "first_model": "..."
                }
              }
            }
          }
        }
    """
    if "profiles" not in data or not isinstance(data["profiles"], dict):
        data["profiles"] = {}
    if profile not in data["profiles"]:
        data["profiles"][profile] = {
            "total_cost": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests": 0,
            "sessions": {},
        }
    return data


def _record_request(
    session_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
) -> None:
    """Record a single API request in the shared state file.

    Called under ``_lock``. Updates both the per-session and
    per-profile aggregate counters.
    """
    profile = _current_profile()
    data = _load_json(_costs_file())
    data = _ensure_structure(data, profile)

    pdata = data["profiles"][profile]
    pdata["total_cost"] = round(pdata["total_cost"] + cost, 6)
    pdata["total_input_tokens"] += input_tokens
    pdata["total_output_tokens"] += output_tokens
    pdata["total_requests"] += 1

    sessions = pdata["sessions"]
    if not isinstance(sessions, dict):
        sessions = {}
        pdata["sessions"] = sessions

    if session_id not in sessions:
        sessions[session_id] = {
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "requests": 0,
            "model_breakdown": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "first_model": model,
        }

    s = sessions[session_id]
    s["cost"] = round(s["cost"] + cost, 6)
    s["input_tokens"] += input_tokens
    s["output_tokens"] += output_tokens
    s["requests"] += 1

    mb = s.get("model_breakdown", {})
    if not isinstance(mb, dict):
        mb = {}
        s["model_breakdown"] = mb
    if model not in mb:
        mb[model] = {
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "requests": 0,
        }
    m = mb[model]
    m["cost"] = round(m["cost"] + cost, 6)
    m["input_tokens"] += input_tokens
    m["output_tokens"] += output_tokens
    m["requests"] += 1

    _atomic_write_json(_costs_file(), data)


# ---------------------------------------------------------------------------
# Token extraction from hook payload
# ---------------------------------------------------------------------------


def _extract_tokens(payload: Any) -> tuple:
    """Extract (model, input_tokens, output_tokens) from a
    ``post_api_request`` payload.

    The payload structure varies by provider and Hermes version. This
    function tries multiple known shapes and returns zeros if nothing
    matches — the plugin must never crash on an unexpected payload.

    Returns ``(model, input_tokens, output_tokens)`` where model is a
    string (possibly empty) and tokens are non-negative ints.
    """
    model = ""
    input_tokens = 0
    output_tokens = 0

    if payload is None:
        return ("", 0, 0)

    # Handle dict payloads
    if isinstance(payload, dict):
        # Try to find model
        model = (
            payload.get("model")
            or payload.get("model_name")
            or payload.get("provider_model")
            or ""
        )

        # Try nested "usage" dict (OpenAI-style)
        usage = payload.get("usage") or payload.get("token_usage") or {}
        if isinstance(usage, dict):
            input_tokens = (
                usage.get("prompt_tokens")
                or usage.get("input_tokens")
                or usage.get("input")
                or 0
            )
            output_tokens = (
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or usage.get("output")
                or 0
            )

        # Try top-level token fields
        if not input_tokens:
            input_tokens = (
                payload.get("input_tokens")
                or payload.get("prompt_tokens")
                or payload.get("input")
                or 0
            )
        if not output_tokens:
            output_tokens = (
                payload.get("output_tokens")
                or payload.get("completion_tokens")
                or payload.get("output")
                or 0
            )

        # Try response nested dict
        if not input_tokens or not output_tokens:
            response = payload.get("response") or {}
            if isinstance(response, dict):
                r_usage = response.get("usage") or {}
                if isinstance(r_usage, dict):
                    input_tokens = input_tokens or r_usage.get("prompt_tokens", 0) or r_usage.get("input_tokens", 0)
                    output_tokens = output_tokens or r_usage.get("completion_tokens", 0) or r_usage.get("output_tokens", 0)

    # Handle objects with attributes (some providers pass dataclasses)
    elif hasattr(payload, "__dict__"):
        model = getattr(payload, "model", "") or getattr(payload, "model_name", "")
        usage = getattr(payload, "usage", None)
        if usage is not None:
            if isinstance(usage, dict):
                input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            else:
                input_tokens = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0)
                output_tokens = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)

    # Coerce to int, defaulting to 0
    try:
        input_tokens = int(input_tokens) if input_tokens else 0
    except (ValueError, TypeError):
        input_tokens = 0
    try:
        output_tokens = int(output_tokens) if output_tokens else 0
    except (ValueError, TypeError):
        output_tokens = 0

    # Ensure non-negative
    input_tokens = max(input_tokens, 0)
    output_tokens = max(output_tokens, 0)

    return (str(model) if model else "", input_tokens, output_tokens)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_cost(cost: float) -> str:
    """Format a cost value for display."""
    if cost < 0.01:
        return f"${cost:.6f}"
    return f"${cost:.4f}"


def _fmt_tokens(n: int) -> str:
    """Format token count with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _get_current_session_id() -> str:
    """Get the current session ID from env or in-memory state."""
    sid = os.environ.get("HERMES_SESSION_ID", "")
    if sid:
        return sid
    with _lock:
        if _current_session:
            return list(_current_session.keys())[-1]
    return "unknown"


# ---------------------------------------------------------------------------
# Slash command handler
# ---------------------------------------------------------------------------


_HELP_TEXT = """\
/cost                    — show current session cost
/cost session            — detailed current session breakdown
/cost profile [name]     — cost summary for a profile (default: current)
/cost fleet              — costs across all profiles
/cost log [N]            — last N cost log entries (default: 20)
/cost reset --confirm    — clear all cost data (requires --confirm)
/cost help               — this message"""


def _handle_slash(raw_args: str) -> Optional[str]:
    """Handle the ``/cost`` slash command.

    Subcommands:
        (none)      — show current session cost summary
        session     — detailed current session breakdown with per-model
        profile [n] — cost summary for profile *n* (defaults to current)
        fleet       — costs across all profiles
        log [N]     — last N entries from cost.log
        reset --confirm — clear all stored data
        help        — show help
    """
    argv = raw_args.strip().split() if raw_args else []
    sub = argv[0] if argv else ""

    # (none) or "help"
    if sub in ("", "help", "-h", "--help"):
        if sub == "help" or sub in ("-h", "--help"):
            return _HELP_TEXT
        # Default: current session cost
        return _cmd_current_session()

    if sub == "session":
        return _cmd_session_detail()

    if sub == "profile":
        name = argv[1] if len(argv) > 1 else _current_profile()
        return _cmd_profile(name)

    if sub == "fleet":
        return _cmd_fleet()

    if sub == "log":
        n = 20
        if len(argv) > 1:
            try:
                n = int(argv[1])
            except ValueError:
                return f"Invalid number: {argv[1]}\n\n{_HELP_TEXT}"
        return _cmd_log(n)

    if sub == "reset":
        if "--confirm" not in argv:
            return "This will delete ALL cost data. Use: /cost reset --confirm"
        return _cmd_reset()

    return f"Unknown subcommand: {sub}\n\n{_HELP_TEXT}"


def _cmd_current_session() -> str:
    """Show a brief cost summary for the current session."""
    sid = _get_current_session_id()
    profile = _current_profile()
    with _lock:
        data = _load_json(_costs_file())
    pdata = data.get("profiles", {}).get(profile, {})
    sdata = pdata.get("sessions", {}).get(sid, {})
    if not sdata:
        return f"No cost data yet for session {sid} (profile: {profile})."
    lines = [
        f"Session: {sid}",
        f"Profile: {profile}",
        f"Cost:   {_fmt_cost(sdata.get('cost', 0.0))}",
        f"Tokens: {_fmt_tokens(sdata.get('input_tokens', 0))} in → "
        f"{_fmt_tokens(sdata.get('output_tokens', 0))} out",
        f"Requests: {sdata.get('requests', 0)}",
    ]
    return "\n".join(lines)


def _cmd_session_detail() -> str:
    """Show detailed breakdown for the current session."""
    sid = _get_current_session_id()
    profile = _current_profile()
    with _lock:
        data = _load_json(_costs_file())
    pdata = data.get("profiles", {}).get(profile, {})
    sdata = pdata.get("sessions", {}).get(sid, {})
    if not sdata:
        return f"No cost data yet for session {sid} (profile: {profile})."
    lines = [
        f"Session: {sid}",
        f"Profile: {profile}",
        f"Started: {sdata.get('started_at', 'unknown')}",
        f"Ended:   {sdata.get('ended_at', '—')}",
        "",
        f"Total cost:    {_fmt_cost(sdata.get('cost', 0.0))}",
        f"Input tokens:  {_fmt_tokens(sdata.get('input_tokens', 0))}",
        f"Output tokens: {_fmt_tokens(sdata.get('output_tokens', 0))}",
        f"Total requests: {sdata.get('requests', 0)}",
        "",
        "Model breakdown:",
    ]
    mb = sdata.get("model_breakdown", {})
    if not mb:
        lines.append("  (no model data)")
    else:
        for model, m in sorted(mb.items(), key=lambda x: -x[1].get("cost", 0)):
            lines.append(
                f"  {model}: "
                f"{_fmt_cost(m.get('cost', 0.0))} | "
                f"{m.get('requests', 0)} req | "
                f"{_fmt_tokens(m.get('input_tokens', 0))} in / "
                f"{_fmt_tokens(m.get('output_tokens', 0))} out"
            )
    return "\n".join(lines)


def _cmd_profile(name: str) -> str:
    """Show cost summary for a specific profile."""
    with _lock:
        data = _load_json(_costs_file())
    pdata = data.get("profiles", {}).get(name, {})
    if not pdata:
        return f"No cost data for profile '{name}'."
    sessions = pdata.get("sessions", {})
    n_sessions = len(sessions)
    lines = [
        f"Profile: {name}",
        f"Total cost:     {_fmt_cost(pdata.get('total_cost', 0.0))}",
        f"Input tokens:   {_fmt_tokens(pdata.get('total_input_tokens', 0))}",
        f"Output tokens:  {_fmt_tokens(pdata.get('total_output_tokens', 0))}",
        f"Total requests:  {pdata.get('total_requests', 0)}",
        f"Sessions:        {n_sessions}",
        "",
    ]
    if n_sessions:
        # Top 5 most expensive sessions
        sorted_sessions = sorted(
            sessions.items(),
            key=lambda x: -x[1].get("cost", 0.0),
        )[:5]
        lines.append("Top 5 most expensive sessions:")
        for sid, s in sorted_sessions:
            lines.append(
                f"  {sid[:24]}...  {_fmt_cost(s.get('cost', 0.0))}  "
                f"({s.get('requests', 0)} req)"
            )
    return "\n".join(lines)


def _cmd_fleet() -> str:
    """Show cost summary across all profiles."""
    with _lock:
        data = _load_json(_costs_file())
    profiles = data.get("profiles", {})
    if not profiles:
        return "No cost data recorded yet."
    lines = ["Fleet Cost Summary", "=" * 40, ""]
    grand_cost = 0.0
    grand_in = 0
    grand_out = 0
    grand_req = 0
    for name in sorted(profiles.keys()):
        p = profiles[name]
        cost = p.get("total_cost", 0.0)
        in_tok = p.get("total_input_tokens", 0)
        out_tok = p.get("total_output_tokens", 0)
        req = p.get("total_requests", 0)
        n_sess = len(p.get("sessions", {}))
        grand_cost += cost
        grand_in += in_tok
        grand_out += out_tok
        grand_req += req
        lines.append(
            f"  {name:20s}  {_fmt_cost(cost):>10s}  "
            f"{req:>6d} req  {n_sess:>4d} sessions"
        )
    lines.append("")
    lines.append("=" * 40)
    lines.append(
        f"  {'TOTAL':20s}  {_fmt_cost(grand_cost):>10s}  "
        f"{grand_req:>6d} req"
    )
    lines.append(
        f"  Tokens: {_fmt_tokens(grand_in)} in → "
        f"{_fmt_tokens(grand_out)} out"
    )
    return "\n".join(lines)


def _cmd_log(n: int) -> str:
    """Show the last N entries from the cost log."""
    log_path = _log_file()
    if not log_path.exists():
        return f"No cost log found at {log_path}"
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading log: {e}"
    # Get last N non-empty lines
    lines = [l.rstrip() for l in lines if l.strip()]
    if not lines:
        return "Cost log is empty."
    n = max(1, min(n, len(lines)))
    return "\n".join(lines[-n:])


def _cmd_reset() -> str:
    """Clear all cost data."""
    with _lock:
        costs = _costs_file()
        log = _log_file()
        for p in (costs, log):
            try:
                if p.exists():
                    p.unlink()
            except Exception as e:
                return f"Error deleting {p}: {e}"
        _append_log("All cost data reset by user.")
    return "All cost data cleared. Log entry recorded."


# ---------------------------------------------------------------------------
# Hook callbacks
# ---------------------------------------------------------------------------


def _on_post_api_request(payload: Any, **kwargs: Any) -> None:
    """Hook: post_api_request — record each API request's cost.

    Extracts model and token counts from the payload, estimates cost,
    and appends to the shared state file. Thread-safe via ``_lock``.

    Never raises — a tracking failure must not break the agent.
    """
    try:
        model, input_tokens, output_tokens = _extract_tokens(payload)
        if input_tokens == 0 and output_tokens == 0:
            # No token info — skip but don't error
            logger.debug("cost-watch: no token info in payload, skipping")
            return

        cost = _estimate_cost(model, input_tokens, output_tokens)
        sid = _get_current_session_id()
        profile = _current_profile()

        with _lock:
            _record_request(sid, model, input_tokens, output_tokens, cost)
            _append_log(
                f"REQ  profile={profile} session={sid[:16]} "
                f"model={model} in={input_tokens} out={output_tokens} "
                f"cost={_fmt_cost(cost)}"
            )
    except Exception as e:
        logger.warning("cost-watch: post_api_request error: %s", e)


def _on_session_start(**kwargs: Any) -> None:
    """Hook: on_session_start — initialize session tracking.

    Records the session start time and logs the event.
    """
    try:
        sid = kwargs.get("session_id") or _get_current_session_id()
        profile = _current_profile()
        with _lock:
            _current_session[sid] = {
                "started_at": datetime.now(timezone.utc).isoformat()
            }
            _append_log(f"START profile={profile} session={sid[:16]}")
    except Exception as e:
        logger.warning("cost-watch: on_session_start error: %s", e)


def _on_session_end(**kwargs: Any) -> None:
    """Hook: on_session_end — finalize session totals and log summary.

    Updates the session's ``ended_at`` timestamp and writes a summary
    line to the cost log.
    """
    try:
        sid = kwargs.get("session_id") or _get_current_session_id()
        profile = _current_profile()
        with _lock:
            # Update ended_at in the state file
            data = _load_json(_costs_file())
            if profile in data.get("profiles", {}):
                sessions = data["profiles"][profile].get("sessions", {})
                if sid in sessions:
                    sessions[sid]["ended_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    _atomic_write_json(_costs_file(), data)
                    s = sessions[sid]
                    _append_log(
                        f"END   profile={profile} session={sid[:16]} "
                        f"cost={_fmt_cost(s.get('cost', 0.0))} "
                        f"reqs={s.get('requests', 0)}"
                    )
            # Clean up in-memory state
            _current_session.pop(sid, None)
    except Exception as e:
        logger.warning("cost-watch: on_session_end error: %s", e)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Register the cost-watch plugin.

    Wires three hooks and one slash command:

    - ``post_api_request`` → :func:`_on_post_api_request`
    - ``on_session_start`` → :func:`_on_session_start`
    - ``on_session_end`` → :func:`_on_session_end`
    - ``/cost`` slash command → :func:`_handle_slash`

    The plugin is fully self-contained — no external dependencies
    beyond the Python standard library. All state is kept in
    ``~/.hermes/cost-watch/`` with atomic writes and thread-safe
    access.
    """
    ctx.register_hook("post_api_request", _on_post_api_request)
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_command(
        "cost",
        handler=_handle_slash,
        description=(
            "Track and display API costs per session and per profile. "
            "Subcommands: session, profile [name], fleet, log [N], reset --confirm"
        ),
    )
    logger.info("cost-watch plugin registered")