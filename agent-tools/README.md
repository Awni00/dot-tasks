# Agent Tools (Reference Assets)

This directory provides reference assets for users who want to integrate the `dot-tasks` package with AI coding agents.

These files are not intended to define or control development workflow for this `dot-tasks` repository itself.

## What's Here

- `skills/dot-tasks/SKILL.md`: canonical skill definition for agent behavior with `dot-tasks`.
- `../src/dot_tasks/resources/agents/task-management-dot-tasks.md`: canonical markdown section for AGENTS policy integration.

## How To Use In Your Agent Setup

1. Copy `skills/dot-tasks/` into your agent's skills directory.
2. Add the canonical task-management section to your repository-level `AGENTS.md`.
3. Adjust project-specific details (naming, thresholds, workflow conventions) as needed.

## Skill File Convention

The skill file follows the standard structure:

- YAML frontmatter with `name` and `description`.
- Markdown sections defining workflow and operating rules.
