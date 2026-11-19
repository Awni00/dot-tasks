---
name: dot-tasks
description: Reference for repositories that track work with the dot-tasks CLI in a repo-local `.tasks/` directory. Use when finding, starting, updating or completing a tracked task, or when deciding whether new work should become a task.
---

# dot-tasks

`dot-tasks` is a Python CLI (assumed installed) that tracks human and agent work in a repo-local `.tasks/` directory.

**This project's task workflow is in `.tasks/README.md`. Read it before working on a task, and follow it.** It says when to create tasks, which files a task keeps, and what to record when wrapping up. This skill only describes the tool.

## Data model

- Each task is a folder `.tasks/<todo|doing|done|trash>/<created-date>-<task_name>/`. The folder moves when the status changes.
- `task.md` holds YAML frontmatter (task_id, task_name, status, dates, priority, effort, spec_readiness, owner, tags, depends_on, blocked_by, due_date) and a Markdown body. The body starts from the sections in `settings.task_body_sections` of `.tasks/config.yaml`.
- The tool writes nothing else. Any other file in a task folder (plans, notes, session records, ...) belongs to the project and is described in `.tasks/README.md`.

## State vs content

- **State** (frontmatter and folder location) changes only through commands: `create`, `start`, `complete`, `update`, `rename`, `delete`. Never edit frontmatter or move task folders by hand.
- **Content** (the `task.md` body and every other file in the task folder) is edited directly, like any file. No command is needed.
- Refer to tasks by name or id, never by folder path. `dot-tasks path <task>` prints the current folder.

## Commands

```bash
dot-tasks list [todo|doing|done|all] [--tag <tag>] --json   # find tasks (default: todo|doing)
dot-tasks view <task> --json                                 # one task, including its path
dot-tasks path <task>                                        # absolute task folder
dot-tasks tags --json                                        # tag counts
dot-tasks graph                                              # dependency graph

dot-tasks create <task_name> --summary "..." [--priority p0|p1|p2|p3] [--effort s|m|l|xl] [--tag <tag>] [--depends-on <task>] [--due-date YYYY-MM-DD]
dot-tasks start <task>                                       # todo -> doing (checks dependencies; --force overrides)
dot-tasks update <task> [--priority ...] [--tag ...] [--depends-on ...] [--status todo|doing|completed] ...
dot-tasks complete <task>                                    # -> done
dot-tasks rename <task> <new_task_name>
dot-tasks delete <task>                                      # move to trash (--hard deletes)
```

`<task>` is a task name or task_id. Pass `--nointeractive` in agent sessions so commands never wait for a prompt.

## Guardrails

- Confirm with the user which task you are working on before starting or completing it; do not bind to a fuzzy match silently.
- Do not restart a `done` task silently; ask whether to create a follow-up task instead.
