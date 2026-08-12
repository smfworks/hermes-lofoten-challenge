"""Tool schemas for skill-forge plugin — what the LLM sees."""

VALIDATE_SKILL = {
    "name": "validate_skill",
    "description": (
        "Validate a Hermes skill by name or path. Checks SKILL.md frontmatter "
        "(required fields: name, description), file structure, description length, "
        "linked file references, and common issues. Returns a structured validation report. "
        "Use this before shipping a skill or when diagnosing skill loading problems."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "Skill name or path to SKILL.md. If a name, searches ~/.hermes/profiles/*/skills/ and ~/.hermes/skills/.",
            },
        },
        "required": ["skill"],
    },
}

VALIDATE_PLUGIN = {
    "name": "validate_plugin",
    "description": (
        "Validate a Hermes plugin by name or path. Checks plugin.yaml manifest, "
        "__init__.py register(ctx) function, schemas.py and tools.py existence, "
        "tool schema completeness (name, description, parameters), and common issues. "
        "Returns a structured validation report."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "plugin": {
                "type": "string",
                "description": "Plugin name or path to plugin directory.",
            },
        },
        "required": ["plugin"],
    },
}

TEST_TOOL_HANDLER = {
    "name": "test_tool_handler",
    "description": (
        "Test a plugin tool handler by loading it and calling with test arguments. "
        "Returns the result, timing, and pass/fail status. Use this to verify "
        "that a tool handler works correctly without starting a full Hermes session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "plugin": {
                "type": "string",
                "description": "Plugin name or path.",
            },
            "tool": {
                "type": "string",
                "description": "Tool function name to test (e.g., 'session_report').",
            },
            "args": {
                "type": "object",
                "description": "Arguments to pass to the handler (default: {}).",
            },
        },
        "required": ["plugin", "tool"],
    },
}

STRESS_TEST_TOOL = {
    "name": "stress_test_tool",
    "description": (
        "Stress test a plugin tool handler with edge-case arguments. Runs the handler "
        "with empty dict, missing required fields, very long strings, unicode, None values, "
        "and other adversarial inputs. Reports which inputs pass, fail, or crash the handler. "
        "Use this to harden plugins before shipping."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "plugin": {
                "type": "string",
                "description": "Plugin name or path.",
            },
            "tool": {
                "type": "string",
                "description": "Tool function name to stress test.",
            },
        },
        "required": ["plugin", "tool"],
    },
}