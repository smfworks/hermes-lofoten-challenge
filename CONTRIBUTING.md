# Contributing

## Tests

Plugins in this monorepo are implemented as `__init__.py` modules. **Do not** run a bare `pytest` over the whole tree in one process without `pytest.ini` — collection order will import the wrong `__init__` and fail tests that pass in isolation.

Correct:

```bash
python -m pytest -q
# uses pytest.ini isolated testpaths

# or one suite:
python -m pytest -q --import-mode=importlib \
  team-maelstrom/hermes-plugin-tool-telemetry/test_tool_telemetry.py
```

## Adding a plugin

1. Put the plugin in `team-<name>/` with `plugin.yaml` and `register(ctx)`.
2. Name the Python module something other than a colliding `__init__` if you add repo-wide collection.
3. Add an isolated test file and list it in `pytest.ini` `testpaths`.
4. Update the README table honestly (test counts must match isolated runs).
