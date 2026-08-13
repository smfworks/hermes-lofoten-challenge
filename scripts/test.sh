#!/usr/bin/env bash
# Isolated suite runner. Plugins are implemented as __init__.py modules;
# collecting them in one pytest process imports the wrong package.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
echo "== telemetry =="
"$PY" -m pytest -q --import-mode=importlib \
  team-maelstrom/hermes-plugin-tool-telemetry/test_tool_telemetry.py
echo "== skill-gap-analyzer =="
"$PY" -m pytest -q --import-mode=importlib \
  team-stockfish/hermes-plugin-skill-gap-analyzer/test_skill_gap_analyzer.py
echo "All isolated suites passed."
