# Contributing

This repository is the **public catalog** for SMF’s Lofoten Hermes skills and plugins. Most new extensions should **not** land as another undocumented sibling repo.

## New skills and plugins

Point new work at **[hermes-extension-forge](https://github.com/smfworks/hermes-extension-forge)** (`extension-forge` skill + `hermes-publish-assistant` plugin): publish gates, docs standards, and an oppositional review harness.

1. Run the forge gates on the package (see that repo’s `hermes-publish-assistant/README.md`).
2. Prefer a governed standalone `hermes-plugin-*` / `hermes-skill-*` repo **or** a well-tested directory in this monorepo — not an empty placeholder.
3. After it is public, update the catalog tables in [README.md](README.md). Status labels must stay honest (`shipped in this monorepo` / `separate repo` / `experimental` / `mock` / `empty`). Do not invent stars or metrics. Do not delete or un-archive sibling repos from here.

### Adding a plugin *in this monorepo*

1. Put the plugin in `team-<name>/` with `plugin.yaml` and `register(ctx)`.
2. Name the Python module something other than a colliding `__init__` if you add repo-wide collection.
3. Add an isolated test file and wire it in `.github/workflows/ci.yml` (and `scripts/test.sh`).
4. Update the README catalog honestly (test claims must match isolated runs).

### Adding a skill *in this monorepo*

1. `team-<name>/skill/SKILL.md` with frontmatter (`name`, `description`, version).
2. Document copy-to-`~/.hermes/skills/<name>/` (or a hub install) in the catalog row.
3. Update README.

## Tests

Plugins in this monorepo are implemented as `__init__.py` modules. **Do not** run a bare `pytest` over the whole tree in one process without isolation — collection order will import the wrong `__init__` and fail tests that pass alone.

Correct:

```bash
./scripts/test.sh

# or one suite:
python -m pytest -q --import-mode=importlib \
  team-maelstrom/hermes-plugin-tool-telemetry/test_tool_telemetry.py
```

`pytest.ini` exists to keep default collection from walking the tree.

## Catalog hygiene

When you change purpose, status, or install steps, edit README in the same PR. If you only verified a sibling via GitHub, say so — do not guess README contents.
