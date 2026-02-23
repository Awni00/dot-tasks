> Reference snippet for package users: this file is meant to be copied/adapted into other repositories that use `dot-tasks`.

# Agent Task Tracking Policy

## Required Skill

Use the local `dot-tasks` skill (`skills/dot-tasks/SKILL.md`) for structured task tracking.

## When To Propose A Task

If requested work is multi-file or likely to take more than 30 minutes, ask the user whether to create a `dot-tasks` task before implementation. A good heuristic for whether a task is large enough to warrant tracking is whether the user enters "plan mode", in which case this should be a question asked during planning.

## During Work

- Use `dot-tasks create` and `dot-tasks start` to enter tracked execution.
- After planning, update the task `plan.md` with implementation steps.
- Record meaningful progress using `dot-tasks update --note`.
- Prefer `dot-tasks` commands over direct edits to task metadata/state files.

## Completion

After implementation and verification, ask the user whether to mark the task completed with `dot-tasks complete`.
