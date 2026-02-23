---
name: dot-tasks
description: Reference skill for users integrating dot-tasks into AI coding agents. Use the dot-tasks CLI to create, manage, and track structured tasks in `.tasks/` so work stays auditable for humans and agents.
---

# dot-tasks Skill

Use this skill whenever task lifecycle tracking is required in a repository that uses `dot-tasks`.

## Workflow

1. Initialize once per repo: `dot-tasks init`.
2. Create a task: `dot-tasks create <task_name> --summary "..."`.
3. Start execution: `dot-tasks start <task_name>`.
4. Keep plan current in `<task>/plan.md`.
5. Record progress: `dot-tasks update <task_name> --note "..."`.
6. Complete work: `dot-tasks complete <task_name>`.

## Required Behavior

- Prefer `task_name` selectors in user-facing interactions.
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
dot-tasks rename <old_name> <new_name>
```

## Data Contract

- Canonical metadata is in `task.md` frontmatter.
- Dependency references use `task_id` in metadata.
- Dependencies are displayed to humans as `task_name (task_id)`.
- `activity.md` line format is `YYYY-MM-DD HH:MM | actor | type | note`.
