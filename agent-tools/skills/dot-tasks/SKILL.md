---
name: dot-tasks
description: Reference skill for users integrating dot-tasks into AI coding agents. Use dot-tasks to track tasks in `.tasks/` with clear, auditable state for humans and agents.
---

# dot-tasks Skill

Use this skill whenever a repository uses `dot-tasks` for task lifecycle tracking.

## When To Use

- For substantial or multi-file work, suggest tracking execution with `dot-tasks`.
- If the user asks what to work on next, use `dot-tasks` task state as the source of truth.

## Default Collaboration Loop

1. Capture task intent with `dot-tasks create <task_name> --summary "..."`.
2. When asked what to work on, inspect `todo`/`doing` via `dot-tasks list` and suggest up to 3 candidate tasks with one-line rationale each.
3. Start active work with `dot-tasks start <task_name>`.
4. Keep progress current with `dot-tasks update <task_name> --note "..."`.
5. Complete with `dot-tasks complete <task_name>` when acceptance criteria are met.

## Working Rules

- Prefer `task_name` selectors in user-facing interactions.
- Prefer `dot-tasks` commands over direct edits to task state files.
- Respect dependency checks; use `--force` only with explicit override intent.
- Use `dot-tasks rename` for renames (never manual folder edits).
- Use `dot-tasks delete` for deletion (soft-delete by default).
- Do not rewrite `activity.md` history; append only.

## Useful Commands

```bash
dot-tasks list
dot-tasks list doing
dot-tasks view <task_name>
dot-tasks update <task_name> --priority p1 --effort l --depends-on <task>
dot-tasks update <task_name> --note "Progress update"
dot-tasks rename <old_name> <new_name>
dot-tasks delete <task_name>
```

## Data Contract

- Canonical metadata is in `task.md` frontmatter.
- Dependency references use `task_id` in metadata.
- Dependencies are displayed to humans as `task_name (task_id)`.
- `activity.md` line format is `YYYY-MM-DD HH:MM | actor | type | note`.
