---
name: dot-tasks
description: Reference for repositories that track work with the dot-tasks CLI in a repo-local `.tasks/` directory. Use when finding, starting, updating or completing a tracked task, or when deciding whether new work should become a task.
---

# dot-tasks

`dot-tasks` is a Python CLI (assumed installed) that tracks human and agent work in a repo-local `.tasks/` directory.

**This project's task workflow is in `.tasks/README.md`. Read it before working on a task, and follow it.** It says when to create tasks, which files a task keeps, and what to record when wrapping up. This skill only describes the tool.

## Data model

- Each task is a folder `.tasks/<todo|doing|done|trash>/<created-date>-<task_name>/`. The folder moves when the status changes.
- `task.md` = YAML frontmatter + a free-form Markdown body:
  - Frontmatter: `task_id`, `task_name`, `summary` (one or two sentences), `status`, dates, `depends_on`, `tags`, then the project's fields from `settings.fields` in `.tasks/config.yaml` (built-ins: `priority`, `effort`, `due_date`, `owner`; projects may define their own).
  - Body: the task description, written directly in an editor. New tasks start from `.tasks/templates/task.md` if it exists, else empty.
- The tool writes nothing else. Any other file in a task folder (plans, notes, session records, ...) belongs to the project and is described in `.tasks/README.md`.

## Editing rules

- **Structural fields** (`task_id`, `task_name`, `status`, dates, `depends_on`, `tags`) change only through commands. Never edit them or move task folders by hand.
- **Value fields** (`summary`, configured fields, custom keys) can be set with `dot-tasks update <task> key=value` or edited by hand; invalid values are reported as warnings.
- **The body and other task files** are edited directly, like any file.
- Refer to tasks by name or id, never by folder path. `dot-tasks path <task>` prints the current folder.

## Commands

```bash
dot-tasks list [todo|doing|done|all] [key=value ...] [--tag <tag>] --json   # find tasks (default: todo|doing)
dot-tasks view <task> --json                                    # one task, including its path
dot-tasks path <task>                                           # absolute task folder
dot-tasks tags --json                                           # tag counts
dot-tasks graph                                                 # dependency graph

dot-tasks create <task_name> summary="..." [field=value ...] [--tag <tag>] [--depends-on <task>]
                                                                # prints the task.md path to write the description in
dot-tasks start <task>                                          # todo -> doing (checks dependencies; --force overrides)
dot-tasks update <task> [field=value ...] [field= ...] [--tag ...] [--depends-on ...] [--status todo|doing|completed]
dot-tasks complete <task>                                       # -> done
dot-tasks rename <task> <new_task_name>
dot-tasks delete <task>                                         # move to trash (--hard deletes)
```

- `<task>` is a task name or task_id. `field=` clears a field; in `list`, `field=` matches unset.
- An unknown field or invalid value is rejected with the configured fields or allowed values.
- Pass `--nointeractive` in agent sessions so commands never wait for a prompt.

## Guardrails

- Confirm with the user which task you are working on before starting or completing it; do not bind to a fuzzy match silently.
- Do not restart a `done` task silently; ask whether to create a follow-up task instead.
