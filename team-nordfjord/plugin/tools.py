"""Tool handlers for session-observability plugin.

All handlers return JSON strings, accept **kwargs, and never raise exceptions.
This is the code that runs when the LLM calls our tools.
"""

import json
import time
import threading
from collections import defaultdict
from pathlib import Path

# Thread-safe session metrics storage
_metrics_lock = threading.Lock()

# Per-session metrics: {session_id: {tool_calls: [...], start_time: float, ...}}
_session_metrics: dict = {}

# Global metrics (all sessions)
_global_metrics = {
    "total_sessions": 0,
    "total_tool_calls": 0,
    "total_errors": 0,
    "tool_usage": defaultdict(int),
    "tool_errors": defaultdict(int),
    "tool_timing": defaultdict(list),
}


def _get_session_id(**kwargs):
    """Extract session ID from kwargs or return 'unknown'."""
    return kwargs.get("task_id") or kwargs.get("session_id") or "unknown"


def _ensure_session(session_id: str):
    """Ensure a session entry exists in _session_metrics."""
    if session_id not in _session_metrics:
        _session_metrics[session_id] = {
            "start_time": time.time(),
            "end_time": None,
            "tool_calls": [],
            "tool_counts": defaultdict(int),
            "tool_errors": defaultdict(int),
            "tool_timing": defaultdict(list),
            "completed": False,
        }


def _get_metrics_dir() -> Path:
    """Get the metrics storage directory."""
    import os
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    metrics_dir = Path(home) / "session-observability"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    return metrics_dir


def _persist_metrics():
    """Persist current metrics to disk (best-effort)."""
    try:
        metrics_dir = _get_metrics_dir()
        data = {
            "global": {
                "total_sessions": _global_metrics["total_sessions"],
                "total_tool_calls": _global_metrics["total_tool_calls"],
                "total_errors": _global_metrics["total_errors"],
                "tool_usage": dict(_global_metrics["tool_usage"]),
                "tool_errors": dict(_global_metrics["tool_errors"]),
                "tool_timing_avg": {
                    k: round(sum(v) / len(v), 2) if v else 0
                    for k, v in _global_metrics["tool_timing"].items()
                },
            },
            "sessions": {
                sid: {
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "completed": s["completed"],
                    "tool_counts": dict(s["tool_counts"]),
                    "tool_errors": dict(s["tool_errors"]),
                    "tool_timing_avg": {
                        k: round(sum(v) / len(v), 2) if v else 0
                        for k, v in s["tool_timing"].items()
                    },
                    "total_calls": len(s["tool_calls"]),
                }
                for sid, s in _session_metrics.items()
            },
        }
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps(data, indent=2, default=str))
    except Exception:
        pass  # Never crash the agent


def record_tool_call(tool_name: str, args: dict, result: str, task_id: str,
                     duration_ms: int = 0, **kwargs):
    """Record a tool call in the session metrics. Called from the hook."""
    with _metrics_lock:
        session_id = task_id or "unknown"
        _ensure_session(session_id)

        # Determine if this was an error
        is_error = False
        try:
            parsed = json.loads(result) if isinstance(result, str) else result
            if isinstance(parsed, dict) and ("error" in parsed or "errors" in parsed):
                is_error = True
        except Exception:
            pass

        # Record in session
        session = _session_metrics[session_id]
        session["tool_calls"].append({
            "tool": tool_name,
            "duration_ms": duration_ms,
            "is_error": is_error,
            "timestamp": time.time(),
        })
        session["tool_counts"][tool_name] += 1
        if is_error:
            session["tool_errors"][tool_name] += 1
        session["tool_timing"][tool_name].append(duration_ms)

        # Record in global
        _global_metrics["total_tool_calls"] += 1
        _global_metrics["tool_usage"][tool_name] += 1
        if is_error:
            _global_metrics["total_errors"] += 1
            _global_metrics["tool_errors"][tool_name] += 1
        _global_metrics["tool_timing"][tool_name].append(duration_ms)

        # Persist periodically (every 10 calls)
        if _global_metrics["total_tool_calls"] % 10 == 0:
            _persist_metrics()


def session_start(session_id: str, **kwargs):
    """Called when a session starts."""
    with _metrics_lock:
        _ensure_session(session_id)
        _session_metrics[session_id]["start_time"] = time.time()
        _session_metrics[session_id]["completed"] = False
        _global_metrics["total_sessions"] += 1


def session_end(session_id: str, **kwargs):
    """Called when a session ends."""
    with _metrics_lock:
        if session_id in _session_metrics:
            _session_metrics[session_id]["end_time"] = time.time()
            _session_metrics[session_id]["completed"] = True
        _persist_metrics()


def session_report(args: dict, **kwargs) -> str:
    """Generate a session observability report."""
    try:
        fmt = args.get("format", "summary")
        session_id = _get_session_id(**kwargs)

        with _metrics_lock:
            session = _session_metrics.get(session_id, {})

            if not session:
                # Try to load from disk
                try:
                    metrics_file = _get_metrics_dir() / "metrics.json"
                    if metrics_file.exists():
                        data = json.loads(metrics_file.read_text())
                        session = data.get("sessions", {}).get(session_id, {})
                        global_data = data.get("global", {})
                    else:
                        global_data = {}
                except Exception:
                    global_data = {}
            else:
                global_data = {
                    "total_sessions": _global_metrics["total_sessions"],
                    "total_tool_calls": _global_metrics["total_tool_calls"],
                    "total_errors": _global_metrics["total_errors"],
                    "tool_usage": dict(_global_metrics["tool_usage"]),
                }

            # Build report
            if fmt == "detailed":
                report = _build_detailed_report(session_id, session, global_data)
            else:
                report = _build_summary_report(session_id, session, global_data)

        return json.dumps(report, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": f"Report generation failed: {e}"})


def _build_summary_report(session_id, session, global_data):
    """Build a compact summary report."""
    total_calls = len(session.get("tool_calls", [])) if session else 0
    tool_counts = session.get("tool_counts", {}) if session else {}
    tool_errors = session.get("tool_errors", {}) if session else {}

    error_count = sum(tool_errors.values()) if tool_errors else 0
    error_rate = round(error_count / total_calls * 100, 1) if total_calls else 0

    # Session duration
    start = session.get("start_time") if session else None
    end = session.get("end_time") if session else None
    duration_s = round(end - start, 1) if start and end else None

    return {
        "session_id": session_id,
        "status": "completed" if session and session.get("completed") else "active" if session else "unknown",
        "duration_seconds": duration_s,
        "total_tool_calls": total_calls,
        "error_count": error_count,
        "error_rate_percent": error_rate,
        "tools_used": dict(tool_counts) if tool_counts else {},
        "global_total_sessions": global_data.get("total_sessions", 0),
        "global_total_tool_calls": global_data.get("total_tool_calls", 0),
    }


def _build_detailed_report(session_id, session, global_data):
    """Build a detailed report with per-tool breakdown."""
    summary = _build_summary_report(session_id, session, global_data)

    tool_calls = session.get("tool_calls", []) if session else []
    tool_timing = session.get("tool_timing", {}) if session else {}

    # Per-tool stats
    per_tool = {}
    for tool_name, count in (session.get("tool_counts", {}) if session else {}).items():
        timings = tool_timing.get(tool_name, [])
        errors = (session.get("tool_errors", {}) if session else {}).get(tool_name, 0)
        per_tool[tool_name] = {
            "calls": count,
            "errors": errors,
            "error_rate": round(errors / count * 100, 1) if count else 0,
            "avg_duration_ms": round(sum(timings) / len(timings), 1) if timings else 0,
            "min_duration_ms": min(timings) if timings else 0,
            "max_duration_ms": max(timings) if timings else 0,
        }

    # Recent calls (last 20)
    recent = tool_calls[-20:] if tool_calls else []

    summary["per_tool_breakdown"] = per_tool
    summary["recent_calls"] = recent
    summary["global_tool_usage"] = dict(global_data.get("tool_usage", {}))
    return summary


def session_health(args: dict, **kwargs) -> str:
    """Check session health and return a score with warnings."""
    try:
        threshold = args.get("threshold", 60)
        session_id = _get_session_id(**kwargs)

        with _metrics_lock:
            session = _session_metrics.get(session_id, {})

        if not session:
            return json.dumps({
                "session_id": session_id,
                "health_score": 100,
                "status": "no_data",
                "warnings": [],
                "recommendations": ["No metrics recorded yet for this session."],
            })

        total_calls = len(session.get("tool_calls", []))
        tool_errors = session.get("tool_errors", {})
        error_count = sum(tool_errors.values()) if tool_errors else 0
        error_rate = error_count / total_calls if total_calls else 0

        # Calculate health score
        score = 100
        warnings = []
        recommendations = []

        # Error rate penalty
        if error_rate > 0.5:
            score -= 40
            warnings.append(f"Critical error rate: {round(error_rate * 100, 1)}%")
            recommendations.append("Investigate failing tools — over half of calls are erroring.")
        elif error_rate > 0.3:
            score -= 25
            warnings.append(f"High error rate: {round(error_rate * 100, 1)}%")
            recommendations.append("Several tools are failing — check error patterns.")
        elif error_rate > 0.1:
            score -= 10
            warnings.append(f"Elevated error rate: {round(error_rate * 100, 1)}%")

        # Slow response penalty
        tool_timing = session.get("tool_timing", {})
        slow_tools = []
        for tool, timings in tool_timing.items():
            avg = sum(timings) / len(timings) if timings else 0
            if avg > 30000:  # > 30 seconds
                slow_tools.append((tool, round(avg / 1000, 1)))
                score -= 5

        if slow_tools:
            warnings.append(f"Slow tools: {', '.join(f'{t} ({s}s avg)' for t, s in slow_tools)}")
            recommendations.append("Consider optimizing or caching slow tool calls.")

        # Too many tool calls (might be stuck in a loop)
        if total_calls > 100:
            score -= 15
            warnings.append(f"Very high tool call count: {total_calls}")
            recommendations.append("Session may be stuck in a loop — consider /reset.")

        score = max(0, min(100, score))
        status = "healthy" if score >= threshold else "degraded"

        return json.dumps({
            "session_id": session_id,
            "health_score": score,
            "status": status,
            "total_calls": total_calls,
            "error_count": error_count,
            "error_rate_percent": round(error_rate * 100, 1),
            "warnings": warnings,
            "recommendations": recommendations,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Health check failed: {e}"})