# Security Policy

This repository contains **local-only** Hermes plugins (SQLite telemetry, skill-library analysis). They are not network services.

## Reporting

Email **aionaedge@agentmail.to**. Do not file public issues for security reports.

## Notes

- Telemetry plugins must redact secrets from stored tool arguments.
- Skill scanners must treat SKILL.md contents as untrusted text, not as instructions to execute.
- Database files belong under the active Hermes profile home, never world-writable shared paths.
