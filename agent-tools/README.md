# Agent Tools (Reference Assets)

This directory provides reference assets for users who want to integrate the `dot-tasks` package with AI coding agents.

These files are not intended to define or control development workflow for this `dot-tasks` repository itself.

## What's Here

- `skills/dot-tasks/SKILL.md`: canonical installable skill definition for `dot-tasks`.
- `AGENTS.md`: reusable policy template describing how agents should use `dot-tasks`.
- `agent.md`: minimal snippet users can paste into their own agent instruction files.

## How To Use In Your Agent Setup

1. Copy `skills/dot-tasks/` into your agent's skills directory.
2. Add the guidance from `AGENTS.md` to your repository agent policy, or paste `agent.md` as a lightweight snippet.
3. Adjust project-specific details (naming, thresholds, workflow conventions) as needed.

## Skill File Convention

The skill file follows the standard structure:

- YAML frontmatter with `name` and `description`.
- Markdown sections defining workflow and operating rules.
