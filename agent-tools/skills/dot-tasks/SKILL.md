---
name: dot-tasks
description: Reference skill for users integrating dot-tasks into AI coding agents. Use dot-tasks to track tasks in `.tasks/` with clear, auditable state for humans and agents.
---

# dot-tasks Skill

Use this skill whenever a repository uses `dot-tasks` for task lifecycle tracking.

## When To Use

- For substantial or multi-file work, suggest tracking execution with `dot-tasks`. A good heuristic is whether the user enters "plan mode" during planning, which should trigger a question about creating a `dot-tasks` task. Check whether a `dot-tasks` task already exists for the work before proposing creation.
- If the user asks what to work on next, use `dot-tasks` task state as the source of truth.

## Default Collaboration Loop

1. Capture task intent with `dot-tasks create <task_name> --summary "..."`.
2. When asked what to work on, inspect `todo`/`doing` via `dot-tasks list` and suggest up to 3 candidate tasks with one-line rationale each.
3. Start active work with `dot-tasks start <task_name>`.
4. Keep progress current with `dot-tasks update <task_name> --note "..."`.
5. Complete with `dot-tasks complete <task_name>` when acceptance criteria are met.

## Commands

```bash
# view help for given command
dot-tasks <command> --help

# list all tasks (optionally, return as json for agent parsing)
dot-tasks list [--json]

# list tasks by status
dot-tasks list [todo|doing|done]

# view details for task by name
dot-tasks view <task_name>

# create a new task with summary
dot-tasks create <task_name> --summary "One-line summary of the task" --priority [p0|p1|p2|p3] --effort [s|m|l] --tag <tag>

# start a task (moves from todo/ to doing/ and creates plan.md)
dot-tasks start <task_name>

# update task metadata, dependencies, or add progress note
dot-tasks update <task_name> --priority p1 --effort l --depends-on <task>

# add a progress note to the task's activity history
dot-tasks update <task_name> --note "Progress update"

# rename a task
dot-tasks rename <old_name> <new_name>

# delete a task (soft-delete by default, use --hard to permanently delete)
dot-tasks delete <task_name>

# complete a task (moves to done/)
dot-tasks complete <task_name>
```

## Working Rules

- Prefer `dot-tasks` commands over direct edits to task state files.
- Direct file edits are allowed for:
  1. `task.md` for writing task summary/specs after `dot-tasks create`.
  2. `plan.md` to keep implementation steps current after `dot-tasks start`.
- Do not rewrite `activity.md` history; append only.
- Respect dependency checks.
- Use `dot-tasks rename` for renames (never manual folder edits).
- Use `dot-tasks delete` for deletion (soft-delete moves to trash/ by default).


## Data Contract

- Canonical metadata is in `task.md` frontmatter.
- Dependency references use `task_id` in metadata.
- Dependencies are displayed to humans as `task_name (task_id)`.
- `activity.md` line format is `YYYY-MM-DD HH:MM | actor | type | note`.
