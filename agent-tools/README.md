# Agent Tools (Reference Assets)

This directory provides reference assets for users who want to integrate the `dot-tasks` package with AI coding agents.

These files are not intended to define or control development workflow for this `dot-tasks` repository itself.

## What's Here

- `skills/dot-tasks/SKILL.md`: canonical skill: a compact reference for the `dot-tasks` data model and commands.
- `../src/dot_tasks/resources/agents/task-management-dot-tasks.md`: canonical markdown section for AGENTS policy integration.

## How To Use In Your Agent Setup

1. Copy `skills/dot-tasks/` into your agent's skills directory.
2. Add the canonical task-management section to your repository-level `AGENTS.md`.
3. Describe your project's workflow (when to create tasks, which files a task keeps, wrap-up and completion rules) in `.tasks/README.md`. Both the skill and the AGENTS section point agents there; `dot-tasks init` writes a starter.

## Skill File Convention

The skill file follows the standard structure:

- YAML frontmatter with `name` and `description`.
- Markdown sections with the data model, the state/content split and the command reference. Workflow belongs to each project's `.tasks/README.md`, not to the skill.
