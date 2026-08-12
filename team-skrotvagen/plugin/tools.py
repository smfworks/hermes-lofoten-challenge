"""Tool handlers for skill-forge plugin.

Validates and stress-tests Hermes skills and plugins using only Python stdlib.
"""

import json
import os
import re
import ast
import time
import importlib.util
import traceback
from pathlib import Path
from collections import defaultdict


def _get_hermes_home() -> str:
    return os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))


def _find_skill(skill_name: str) -> Path:
    """Find a skill by name, searching common locations."""
    home = _get_hermes_home()
    search_paths = [
        Path(home) / "profiles" / "nemo" / "skills",
        Path(home) / "skills",
    ]

    # If it's a path, use directly
    p = Path(skill_name)
    if p.exists():
        if p.is_file() and p.name == "SKILL.md":
            return p
        if p.is_dir() and (p / "SKILL.md").exists():
            return p / "SKILL.md"

    # Search by name
    for base in search_paths:
        if not base.exists():
            continue
        # Recursively find SKILL.md files matching the name
        for skmd in base.rglob("SKILL.md"):
            if skill_name.lower() in str(skmd.parent.name).lower():
                return skmd
        # Also check directory names
        for d in base.rglob(skill_name):
            if d.is_dir() and (d / "SKILL.md").exists():
                return d / "SKILL.md"

    return None


def _find_plugin(plugin_name: str) -> Path:
    """Find a plugin by name or path."""
    home = _get_hermes_home()
    search_paths = [
        Path(home) / "plugins",
        Path(home) / "hermes-agent" / "plugins",
    ]

    # If it's a path, use directly
    p = Path(plugin_name)
    if p.exists() and p.is_dir():
        if (p / "plugin.yaml").exists():
            return p
    if p.exists() and p.is_file() and p.name == "plugin.yaml":
        return p.parent

    # Search by name
    for base in search_paths:
        if not base.exists():
            continue
        candidate = base / plugin_name
        if candidate.is_dir() and (candidate / "plugin.yaml").exists():
            return candidate
        # Also search subdirectories (category/name)
        for d in base.rglob(plugin_name):
            if d.is_dir() and (d / "plugin.yaml").exists():
                return d

    return None


def _parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from a SKILL.md file. Returns (frontmatter_dict, body_str)."""
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end = content.find("---", 3)
    if end == -1:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()

    # Simple YAML parsing (no external deps)
    fm = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item
        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip()
            if current_list is None:
                current_list = []
            current_list.append(value)
            fm[current_key] = current_list
            continue

        # Key-value
        if ":" in stripped:
            if current_list is not None:
                current_list = None
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                fm[key] = value
                current_key = key
                current_list = None
            else:
                current_key = key
                current_list = []

    return fm, body


def validate_skill(args: dict, **kwargs) -> str:
    """Validate a Hermes skill."""
    try:
        skill_name = args.get("skill", "")
        if not skill_name:
            return json.dumps({"error": "No skill name provided"})

        skill_path = _find_skill(skill_name)
        if not skill_path:
            return json.dumps({
                "skill": skill_name,
                "valid": False,
                "errors": [f"Skill not found: {skill_name}"],
                "warnings": [],
                "info": [],
            })

        content = skill_path.read_text()
        fm, body = _parse_frontmatter(content)

        errors = []
        warnings = []
        info = []

        # Required fields
        if "name" not in fm:
            errors.append("Missing required frontmatter field: name")
        if "description" not in fm:
            errors.append("Missing required frontmatter field: description")
        if "version" not in fm:
            warnings.append("Missing recommended field: version")

        # Description length (truncated at 57 chars in system prompt)
        desc = fm.get("description", "")
        if len(desc) > 57:
            warnings.append(f"Description is {len(desc)} chars — truncated to 57 in system prompt index. First 57: '{desc[:57]}...'")

        # Check for body content
        if len(body) < 100:
            warnings.append("Skill body is very short (< 100 chars) — may lack sufficient instructions")

        # Check for linked files references
        linked_refs = re.findall(r'(?:references|templates|scripts|assets)/[^\s)"]+', body)
        skill_dir = skill_path.parent
        for ref in linked_refs:
            ref_path = skill_dir / ref
            if not ref_path.exists():
                warnings.append(f"Linked file reference not found: {ref}")

        # Check for ambiguous instructions
        ambiguous = ["handle it appropriately", "do the right thing", "as appropriate",
                     "use your judgment", "handle errors gracefully"]
        for phrase in ambiguous:
            if phrase.lower() in body.lower():
                warnings.append(f"Potentially ambiguous instruction: '{phrase}'")

        # Check for hardcoded paths
        hardcoded = re.findall(r'~/\S+|/home/\S+', body)
        if hardcoded:
            info.append(f"Contains {len(hardcoded)} hardcoded path references (consider using get_hermes_home())")

        # File structure info
        files_in_dir = list(skill_dir.iterdir()) if skill_dir.is_dir() else []
        info.append(f"Skill directory: {skill_dir}")
        info.append(f"Files: {[f.name for f in files_in_dir]}")

        valid = len(errors) == 0

        return json.dumps({
            "skill": fm.get("name", skill_name),
            "path": str(skill_path),
            "valid": valid,
            "frontmatter": fm,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "body_length": len(body),
            "description_length": len(desc),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Validation failed: {e}"})


def validate_plugin(args: dict, **kwargs) -> str:
    """Validate a Hermes plugin."""
    try:
        plugin_name = args.get("plugin", "")
        if not plugin_name:
            return json.dumps({"error": "No plugin name provided"})

        plugin_path = _find_plugin(plugin_name)
        if not plugin_path:
            return json.dumps({
                "plugin": plugin_name,
                "valid": False,
                "errors": [f"Plugin not found: {plugin_name}"],
                "warnings": [],
                "info": [],
            })

        errors = []
        warnings = []
        info = []

        # Check required files
        required_files = ["plugin.yaml", "__init__.py"]
        for f in required_files:
            if not (plugin_path / f).exists():
                errors.append(f"Missing required file: {f}")

        # Check optional files
        optional_files = ["schemas.py", "tools.py"]
        for f in optional_files:
            if not (plugin_path / f).exists():
                warnings.append(f"Missing optional file: {f}")

        # Parse plugin.yaml
        manifest = {}
        yaml_path = plugin_path / "plugin.yaml"
        if yaml_path.exists():
            yaml_content = yaml_path.read_text()
            for line in yaml_content.split("\n"):
                stripped = line.strip()
                if ":" in stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                    key, _, value = stripped.partition(":")
                    manifest[key.strip()] = value.strip().strip('"').strip("'")

        # Check manifest fields
        if "name" not in manifest:
            errors.append("plugin.yaml missing 'name' field")
        if "version" not in manifest:
            warnings.append("plugin.yaml missing 'version' field")
        if "description" not in manifest:
            warnings.append("plugin.yaml missing 'description' field")

        # Check __init__.py for register function
        init_path = plugin_path / "__init__.py"
        if init_path.exists():
            init_content = init_path.read_text()
            if "def register(ctx)" not in init_content and "def register(ctx:" not in init_content:
                errors.append("__init__.py missing register(ctx) function")

            # Check for ctx.register_tool calls
            tool_registrations = re.findall(r'ctx\.register_tool\s*\(\s*name\s*=\s*["\']([^"\']+)', init_content)
            info.append(f"Tools registered: {tool_registrations}")

            # Check for ctx.register_hook calls
            hook_registrations = re.findall(r'ctx\.register_hook\s*\(\s*["\']([^"\']+)', init_content)
            info.append(f"Hooks registered: {hook_registrations}")

            # Check for ctx.register_command calls
            cmd_registrations = re.findall(r'ctx\.register_command\s*\(\s*["\']([^"\']+)', init_content)
            info.append(f"Commands registered: {cmd_registrations}")

        # Check schemas.py for valid tool schemas
        schemas_path = plugin_path / "schemas.py"
        if schemas_path.exists():
            schemas_content = schemas_path.read_text()
            # Find schema definitions (uppercase variables)
            schema_names = re.findall(r'^([A-Z_]+)\s*=\s*{', schemas_content, re.MULTILINE)
            for sn in schema_names:
                info.append(f"Schema found: {sn}")

            # Check each schema has required fields
            for sn in schema_names:
                # Extract the schema dict
                pattern = rf'{sn}\s*=\s*\{{(.*?)\}}'
                match = re.search(pattern, schemas_content, re.DOTALL)
                if match:
                    schema_text = match.group(1)
                    if '"name"' not in schema_text and "'name'" not in schema_text:
                        warnings.append(f"Schema {sn} missing 'name' field")
                    if '"description"' not in schema_text and "'description'" not in schema_text:
                        warnings.append(f"Schema {sn} missing 'description' field")
                    if '"parameters"' not in schema_text and "'parameters'" not in schema_text:
                        warnings.append(f"Schema {sn} missing 'parameters' field")

        # Check tools.py for handler patterns
        tools_path = plugin_path / "tools.py"
        if tools_path.exists():
            tools_content = tools_path.read_text()
            # Find function definitions
            handler_funcs = re.findall(r'^def\s+(\w+)\s*\(\s*args\s*:', tools_content, re.MULTILINE)
            info.append(f"Handler functions: {handler_funcs}")

            # Check for **kwargs
            for func in handler_funcs:
                if f"def {func}(args:" in tools_content and "**kwargs" not in tools_content.split(f"def {func}")[1].split("def ")[0]:
                    warnings.append(f"Handler '{func}' missing **kwargs in signature")

            # Check for json.dumps returns
            if "json.dumps" not in tools_content:
                warnings.append("tools.py doesn't use json.dumps — handlers must return JSON strings")

        valid = len(errors) == 0

        return json.dumps({
            "plugin": manifest.get("name", plugin_name),
            "path": str(plugin_path),
            "valid": valid,
            "manifest": manifest,
            "errors": errors,
            "warnings": warnings,
            "info": info,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Validation failed: {e}"})


def _load_plugin_module(plugin_path: Path):
    """Load a plugin's tools.py module dynamically."""
    tools_path = plugin_path / "tools.py"
    if not tools_path.exists():
        return None

    module_name = f"skill_forge_test_{plugin_path.name}"
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tool_handler(args: dict, **kwargs) -> str:
    """Test a plugin tool handler with given arguments."""
    try:
        plugin_name = args.get("plugin", "")
        tool_name = args.get("tool", "")
        test_args = args.get("args", {})

        if not plugin_name or not tool_name:
            return json.dumps({"error": "Need 'plugin' and 'tool' parameters"})

        plugin_path = _find_plugin(plugin_name)
        if not plugin_path:
            return json.dumps({"error": f"Plugin not found: {plugin_name}"})

        mod = _load_plugin_module(plugin_path)
        if not mod:
            return json.dumps({"error": f"Could not load tools.py from {plugin_path}"})

        if not hasattr(mod, tool_name):
            return json.dumps({"error": f"Tool '{tool_name}' not found in {plugin_path.name}/tools.py"})

        handler = getattr(mod, tool_name)

        # Call the handler
        start = time.time()
        try:
            result = handler(test_args)
            elapsed_ms = round((time.time() - start) * 1000, 2)

            # Verify result is a JSON string
            is_json = False
            parsed = None
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    is_json = True
                except json.JSONDecodeError:
                    pass

            return json.dumps({
                "plugin": plugin_path.name,
                "tool": tool_name,
                "args": test_args,
                "result": result if not is_json else parsed,
                "is_json_string": is_json,
                "elapsed_ms": elapsed_ms,
                "status": "PASS" if is_json else "FAIL",
                "error": None if is_json else "Handler did not return valid JSON string",
            }, indent=2)
        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000, 2)
            return json.dumps({
                "plugin": plugin_path.name,
                "tool": tool_name,
                "args": test_args,
                "result": None,
                "is_json_string": False,
                "elapsed_ms": elapsed_ms,
                "status": "CRASH",
                "error": str(e),
                "traceback": traceback.format_exc()[:500],
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Test failed: {e}"})


def stress_test_tool(args: dict, **kwargs) -> str:
    """Stress test a plugin tool handler with edge-case arguments."""
    try:
        plugin_name = args.get("plugin", "")
        tool_name = args.get("tool", "")

        if not plugin_name or not tool_name:
            return json.dumps({"error": "Need 'plugin' and 'tool' parameters"})

        plugin_path = _find_plugin(plugin_name)
        if not plugin_path:
            return json.dumps({"error": f"Plugin not found: {plugin_name}"})

        mod = _load_plugin_module(plugin_path)
        if not mod:
            return json.dumps({"error": f"Could not load tools.py from {plugin_path}"})

        if not hasattr(mod, tool_name):
            return json.dumps({"error": f"Tool '{tool_name}' not found"})

        handler = getattr(mod, tool_name)

        # Edge case test suites
        edge_cases = [
            ("empty_dict", {}),
            ("None_args", {"args": None}),
            ("missing_required", {"nonexistent_param": "value"}),
            ("empty_string", {"text": "", "query": "", "skill": "", "plugin": ""}),
            ("very_long_string", {"text": "x" * 10000, "query": "x" * 10000}),
            ("unicode", {"text": "Lofoten — 洛福滕 — Лофотен — 🏔️🐟", "query": "洛福滕"}),
            ("None_values", {"text": None, "query": None, "skill": None, "plugin": None}),
            ("numeric_as_string", {"text": 12345, "query": 12345}),
            ("nested_dict", {"args": {"deep": {"nested": {"value": True}}}}),
            ("boolean_true", {"persist": True, "format": True}),
            ("boolean_false", {"persist": False, "format": False}),
            ("special_chars", {"text": "'; DROP TABLE-- <script>alert(1)</script>", "query": "'; --"}),
        ]

        results = []
        pass_count = 0
        fail_count = 0
        crash_count = 0

        for case_name, case_args in edge_cases:
            start = time.time()
            try:
                result = handler(case_args)
                elapsed_ms = round((time.time() - start) * 1000, 2)

                is_json = isinstance(result, str)
                if is_json:
                    try:
                        json.loads(result)
                    except json.JSONDecodeError:
                        is_json = False

                status = "PASS" if is_json else "FAIL"
                if status == "PASS":
                    pass_count += 1
                else:
                    fail_count += 1

                results.append({
                    "case": case_name,
                    "status": status,
                    "elapsed_ms": elapsed_ms,
                    "result_preview": str(result)[:200] if result else "None",
                })
            except Exception as e:
                elapsed_ms = round((time.time() - start) * 1000, 2)
                crash_count += 1
                results.append({
                    "case": case_name,
                    "status": "CRASH",
                    "elapsed_ms": elapsed_ms,
                    "error": str(e)[:200],
                })

        return json.dumps({
            "plugin": plugin_path.name,
            "tool": tool_name,
            "total_cases": len(edge_cases),
            "passed": pass_count,
            "failed": fail_count,
            "crashed": crash_count,
            "pass_rate": round(pass_count / len(edge_cases) * 100, 1),
            "results": results,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Stress test failed: {e}"})