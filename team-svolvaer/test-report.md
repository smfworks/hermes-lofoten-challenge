# Test Report — Team Svolvær Deliverables

**Date:** 2026-08-11  
**Team:** Svolvær — Liam (CDO), Harry (Editor), Jeff (Developer)  
**Challenge:** SMF Works Lofoten Challenge — Session Intelligence  

---

## Deliverables

| # | Deliverable | Path | Status |
|---|---|---|---|
| 1 | SKILL: session-analytics | `team-svolvaer/skill/SKILL.md` | ✅ Complete |
| 2 | PLUGIN: cost-watch | `team-svolvaer/plugin/` | ✅ Complete |

---

## Test Results

### 1. Python Syntax Validation

```
python3 -c "import ast; ast.parse(open('plugin/__init__.py').read())"
```

**Result:** ✅ PASS (exit code 0)  
No syntax errors detected.

### 2. YAML Validation

```
python3 -c "import yaml; yaml.safe_load(open('plugin/plugin.yaml'))"
```

**Result:** ✅ PASS (exit code 0)  
YAML parses cleanly. All required fields present: name, version, description, author, hooks.

### 3. Module Import Test

**Result:** ✅ PASS  
Module imports successfully. `register(ctx)` function is present and callable.

### 4. Edge Case Tests (23 tests)

| Test | Description | Result |
|---|---|---|
| Empty/missing file | `_load_json` on non-existent path returns `{}` | ✅ |
| Corrupted JSON | `_load_json` on invalid JSON returns `{}` | ✅ |
| Non-dict JSON (list) | `_load_json` on `[1,2,3]` returns `{}` | ✅ |
| Extract tokens from None | Returns `("", 0, 0)` | ✅ |
| Extract tokens from empty dict | Returns `("", 0, 0)` | ✅ |
| Extract tokens OpenAI-style | Parses `usage.prompt_tokens` / `completion_tokens` | ✅ |
| Extract tokens Anthropic-style | Parses `usage.input_tokens` / `output_tokens` | ✅ |
| Cost estimation gpt-4o | Correct rate calculation | ✅ |
| Cost estimation unknown model | Falls back to default rate | ✅ |
| Prefix match versioned model | `gpt-4o-2024-08-06` matches `gpt-4o` | ✅ |
| Empty model cost rate | Returns fallback rates | ✅ |
| Slash help | Returns help text with subcommands | ✅ |
| Slash no-args | Returns current session info | ✅ |
| Unknown subcommand | Returns error + help | ✅ |
| Reset without --confirm | Rejected with instructions | ✅ |
| ensure_structure | Creates nested profile dict | ✅ |
| Profile from HERMES_HOME | Extracts "myprofile" from path | ✅ |
| Profile fallback | Returns "default" when no HERMES_HOME | ✅ |
| Small cost formatting | `$0.000010` for tiny values | ✅ |
| Large cost formatting | `$1.5000` for larger values | ✅ |
| Token formatting K | `1.5K` for 1500 | ✅ |
| Token formatting M | `2.5M` for 2500000 | ✅ |
| Token formatting small | `500` for sub-1000 values | ✅ |

**Summary: 23/23 passed**

### 5. Integration & Concurrency Tests (27 tests)

| Test | Description | Result |
|---|---|---|
| Full session lifecycle | start → 3 API requests → end | ✅ |
| Data file written | `costs.json` exists after requests | ✅ |
| Profile exists in data | `testprofile` key present | ✅ |
| Profile request count | 3 total requests | ✅ |
| Profile cost positive | Cost > 0 after requests | ✅ |
| Profile token totals | 3500 input, 1700 output | ✅ |
| Session exists | `test-sess-001` in sessions dict | ✅ |
| Session request count | 3 requests | ✅ |
| Session ended_at set | Timestamp recorded on end | ✅ |
| Session model breakdown | 3 models tracked | ✅ |
| gpt-4o in breakdown | Per-model tracking works | ✅ |
| Log file created | `cost.log` exists | ✅ |
| Log START entry | Session start logged | ✅ |
| Log 3 REQ entries | All requests logged | ✅ |
| Log END entry | Session end logged | ✅ |
| Slash current session | Shows cost with `$` symbol | ✅ |
| Slash session detail | Shows model breakdown | ✅ |
| Slash profile | Shows profile summary | ✅ |
| Slash fleet | Shows fleet-wide totals | ✅ |
| Slash log | Shows log entries | ✅ |
| Concurrent: no errors | 10 threads × 10 requests, no exceptions | ✅ |
| Concurrent: 100 requests | All 100 recorded correctly | ✅ |
| Reset returns success | "cleared" in output | ✅ |
| Data deleted after reset | `costs.json` removed | ✅ |
| Fleet with no data | Graceful "No cost data" message | ✅ |
| Profile with no data | Graceful "No cost data" message | ✅ |
| Log with no file | Graceful "No cost log found" message | ✅ |

**Summary: 27/27 passed**

---

## Test Summary

| Category | Tests | Passed | Failed |
|---|---|---|---|
| Syntax & YAML | 2 | 2 | 0 |
| Module import | 1 | 1 | 0 |
| Edge cases | 23 | 23 | 0 |
| Integration & concurrency | 27 | 27 | 0 |
| **Total** | **53** | **53** | **0** |

All tests pass. No failures.

---

## Key Design Decisions

1. **Atomic writes** — All JSON state writes go through `.tmp` → `os.replace()`, ensuring the file is never partially written.
2. **Thread safety** — A module-level `threading.Lock()` guards all shared state access (in-memory cache + file I/O). Verified with 10 concurrent threads × 10 requests = 100 total, all recorded correctly.
3. **Graceful degradation** — Every external operation (file I/O, token extraction, cost estimation) is wrapped in try/except. The plugin never raises into the agent. Corrupted JSON, missing files, and unexpected payload shapes all return safe defaults.
4. **Global storage** — Data stored at `~/.hermes/cost-watch/` (global level, not per-profile), derived from `HERMES_HOME` by walking up to find the `.hermes` root. This enables the `/cost fleet` command to see all profiles.
5. **Token extraction** — Handles multiple payload shapes: OpenAI (`prompt_tokens`/`completion_tokens`), Anthropic (`input_tokens`/`output_tokens`), nested `usage` dicts, top-level fields, and attribute-based objects. Falls back to `(0, 0)` if nothing matches.
6. **Cost estimation** — Simple per-1K-token rate table for 20+ common models. Unknown models fall back to a default rate. Versioned model names (e.g. `gpt-4o-2024-08-06`) are matched via prefix lookup.

## Lofoten Connection

The plugin and skill are inspired by the stockfish (tørrfisk) trade routes that connected Lofoten to Venice for over 800 years. Just as every shipment of dried cod was logged, weighed, and accounted for across harbors from Bergen to the Rialto, the cost-watch plugin logs every API request, weighs every token, and accounts for every dollar spent — documenting the value exchange of agent work.