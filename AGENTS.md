# Agent Task Tracking Policy

## Required Skill

Use the local `dot-tasks` skill (`/Users/awni/Documents/project-code/dot-tasks/SKILL.md`) for structured task tracking.

## When To Propose A Task

If requested work is multi-file or likely to take more than 30 minutes, ask the user whether to create a `dot-tasks` task before implementation.

## During Work

- Use `dot-tasks create` and `dot-tasks start` to enter tracked execution.
- After planning, update the task `plan.md` with implementation steps.
- Record meaningful progress using `dot-tasks update --note`.
- Prefer `dot-tasks` commands over direct edits to task metadata/state files.

## Completion

After implementation and verification, ask the user whether to mark the task completed with `dot-tasks complete`.
